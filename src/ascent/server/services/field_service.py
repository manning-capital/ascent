import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ascent.database.models import (
    Asset,
    AssetMetadata,
    AssetType,
    AssetTypeMetadata,
    AssetTypeProviderAssetMetadata,
    Attribute,
    Composite,
    CompositeAttribute,
    CompositeMember,
    CompositeMetadata,
    CompositePeriodAttribute,
    FeedCompositeScope,
    FeedInstrumentScope,
    Instrument,
    InstrumentMetadata,
    Metadata,
    Order,
    Provider,
    ProviderAssetMetadata,
    ProviderMetadata,
    ProviderType,
    ProviderTypeMetadata,
    StrategyCompositeScope,
    StrategyInstrumentScope,
    TradeLeg,
)
from ascent.database.models.instruments import (
    InstrumentAttribute,
    InstrumentPeriodAttribute,
)
from ascent.database.models.portfolio import PortfolioAssetHolding
from ascent.database.models.provider_content import (
    AssetContent,
    ProviderContent,
    ProviderContentAttribute,
    ProviderContentMetadata,
)
from ascent.database.models.transactions import Transaction
from ascent.server.exceptions import BadRequestError, ConflictError, NotFoundError
from ascent.server.schemas.attributes import AttributeCreate, AttributeUpdate
from ascent.server.schemas.metadata import (
    EntityUsage,
    EntityUsageItem,
    MetadataTypeCreate,
    MetadataTypeUpdate,
)


def _count(db: Session, model, column, value) -> int:
    result = db.execute(select(func.count()).where(column == value)).scalar()
    return result or 0


def _count_in(db: Session, column, values: list) -> int:
    """Count rows where column is in a list of values."""
    if not values:
        return 0
    result = db.execute(select(func.count()).where(column.in_(values))).scalar()
    return result or 0


def _count_or_in(db: Session, columns: list, values: list) -> int:
    """Count rows where any of the columns is in a list of values."""
    if not values:
        return 0
    result = db.execute(
        select(func.count()).where(or_(*(col.in_(values) for col in columns)))
    ).scalar()
    return result or 0


def _build_usage(items: list[tuple[str, int, str]]) -> EntityUsage:
    """Build EntityUsage from (label, count, kind) tuples."""
    usage_items = [
        EntityUsageItem(label=label, count=count, kind=kind) for label, count, kind in items
    ]
    return EntityUsage(items=usage_items, total=sum(c for _, c, _ in items))


def _get_asset_ids_for_type(db: Session, asset_type_id: uuid.UUID) -> list:
    """Get all asset IDs belonging to a given asset type."""
    rows = db.execute(select(Asset.id).where(Asset.asset_type_id == asset_type_id)).scalars().all()
    return list(rows)


def _get_provider_ids_for_type(db: Session, provider_type_id: uuid.UUID) -> list:
    """Get all provider IDs belonging to a given provider type."""
    rows = (
        db.execute(select(Provider.id).where(Provider.provider_type_id == provider_type_id))
        .scalars()
        .all()
    )
    return list(rows)


def _count_asset_cascade(db: Session, asset_ids: list) -> list[tuple[str, int, str]]:
    """Count all data affected when deleting a set of assets. Returns (label, count, kind)."""
    if not asset_ids:
        return []
    return [
        ("Asset Metadata", _count_in(db, AssetMetadata.asset_id, asset_ids), "cascade"),
        (
            "Provider-Asset Metadata",
            _count_in(db, ProviderAssetMetadata.asset_id, asset_ids),
            "cascade",
        ),
        (
            "Instruments (from_asset)",
            _count_in(db, Instrument.from_asset_id, asset_ids),
            "reference",
        ),
        (
            "Instruments (to_asset)",
            _count_in(db, Instrument.to_asset_id, asset_ids),
            "reference",
        ),
        ("Asset Content Links", _count_in(db, AssetContent.asset_id, asset_ids), "cascade"),
        ("Portfolio Holdings", _count_in(db, PortfolioAssetHolding.asset_id, asset_ids), "cascade"),
        (
            "Transactions",
            _count_or_in(db, [Transaction.from_asset_id, Transaction.to_asset_id], asset_ids),
            "cascade",
        ),
    ]


def _count_provider_cascade(db: Session, provider_ids: list) -> list[tuple[str, int, str]]:
    """Count all data affected when deleting a set of providers. Returns (label, count, kind)."""
    if not provider_ids:
        return []
    return [
        ("Provider Metadata", _count_in(db, ProviderMetadata.provider_id, provider_ids), "cascade"),
        (
            "Provider-Asset Metadata",
            _count_in(db, ProviderAssetMetadata.provider_id, provider_ids),
            "cascade",
        ),
        (
            "Instruments",
            _count_in(db, Instrument.provider_id, provider_ids),
            "reference",
        ),
        ("Content", _count_in(db, ProviderContent.provider_id, provider_ids), "cascade"),
    ]


def _delete_assets_cascade(db: Session, asset_ids: list) -> None:
    """Delete all data referencing the given asset IDs, then the assets themselves."""
    if not asset_ids:
        return
    for tbl, col in [
        (AssetMetadata, AssetMetadata.asset_id),
        (ProviderAssetMetadata, ProviderAssetMetadata.asset_id),
        (AssetContent, AssetContent.asset_id),
        (PortfolioAssetHolding, PortfolioAssetHolding.asset_id),
    ]:
        db.execute(tbl.__table__.delete().where(col.in_(asset_ids)))
    for tbl, cols in [
        (
            Instrument,
            [Instrument.from_asset_id, Instrument.to_asset_id],
        ),
        (Transaction, [Transaction.from_asset_id, Transaction.to_asset_id]),
    ]:
        db.execute(tbl.__table__.delete().where(or_(*(c.in_(asset_ids) for c in cols))))
    # Clear self-references before deleting
    db.execute(
        Asset.__table__.update()
        .where(Asset.underlying_asset_id.in_(asset_ids))
        .values(underlying_asset_id=None)
    )
    db.execute(Asset.__table__.delete().where(Asset.id.in_(asset_ids)))


def _delete_providers_cascade(db: Session, provider_ids: list) -> None:
    """Delete all data referencing the given provider IDs, then the providers themselves."""
    if not provider_ids:
        return
    for tbl, col in [
        (ProviderMetadata, ProviderMetadata.provider_id),
        (ProviderAssetMetadata, ProviderAssetMetadata.provider_id),
        (Instrument, Instrument.provider_id),
        (ProviderContent, ProviderContent.provider_id),
    ]:
        db.execute(tbl.__table__.delete().where(col.in_(provider_ids)))
    # Clear self-references before deleting
    db.execute(
        Provider.__table__.update()
        .where(Provider.underlying_provider_id.in_(provider_ids))
        .values(underlying_provider_id=None)
    )
    db.execute(Provider.__table__.delete().where(Provider.id.in_(provider_ids)))


# ---------------------------------------------------------------------------
# Metadata Types
# ---------------------------------------------------------------------------


def get_metadata_types(db: Session) -> list[Metadata]:
    return list(db.execute(select(Metadata)).scalars().all())


def get_metadata_type(db: Session, metadata_id: uuid.UUID) -> Metadata:
    obj = db.get(Metadata, metadata_id)
    if not obj:
        raise NotFoundError("Metadata type not found")
    return obj


def create_metadata_type(db: Session, data: MetadataTypeCreate) -> Metadata:
    existing = db.execute(select(Metadata).where(Metadata.name == data.name)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Metadata type with name '{data.name}' already exists")
    obj = Metadata(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_metadata_type(db: Session, metadata_id: uuid.UUID, data: MetadataTypeUpdate) -> Metadata:
    obj = get_metadata_type(db, metadata_id)
    updates = data.model_dump(exclude_none=True)
    if "name" in updates and updates["name"] != obj.name:
        existing = db.execute(
            select(Metadata).where(Metadata.name == updates["name"])
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(f"Metadata type with name '{updates['name']}' already exists")
    for key, val in updates.items():
        setattr(obj, key, val if not isinstance(val, type) else val.value)
    db.commit()
    db.refresh(obj)
    return obj


def get_metadata_type_usage(db: Session, metadata_id: uuid.UUID) -> EntityUsage:
    get_metadata_type(db, metadata_id)
    return _build_usage(
        [
            (
                "Asset Metadata",
                _count(db, AssetMetadata, AssetMetadata.metadata_id, metadata_id),
                "cascade",
            ),
            (
                "Provider Metadata",
                _count(db, ProviderMetadata, ProviderMetadata.metadata_id, metadata_id),
                "cascade",
            ),
            (
                "Provider-Asset Metadata",
                _count(db, ProviderAssetMetadata, ProviderAssetMetadata.metadata_id, metadata_id),
                "cascade",
            ),
            (
                "Content Metadata",
                _count(
                    db, ProviderContentMetadata, ProviderContentMetadata.metadata_id, metadata_id
                ),
                "cascade",
            ),
            (
                "Asset Type Fields",
                _count(db, AssetTypeMetadata, AssetTypeMetadata.metadata_id, metadata_id),
                "cascade",
            ),
            (
                "Provider Type Fields",
                _count(db, ProviderTypeMetadata, ProviderTypeMetadata.metadata_id, metadata_id),
                "cascade",
            ),
            (
                "Provider-Asset Type Fields",
                _count(
                    db,
                    AssetTypeProviderAssetMetadata,
                    AssetTypeProviderAssetMetadata.metadata_id,
                    metadata_id,
                ),
                "cascade",
            ),
        ]
    )


def delete_metadata_type(db: Session, metadata_id: uuid.UUID) -> None:
    obj = get_metadata_type(db, metadata_id)
    for model, col in [
        (AssetMetadata, AssetMetadata.metadata_id),
        (ProviderMetadata, ProviderMetadata.metadata_id),
        (ProviderAssetMetadata, ProviderAssetMetadata.metadata_id),
        (ProviderContentMetadata, ProviderContentMetadata.metadata_id),
        (AssetTypeMetadata, AssetTypeMetadata.metadata_id),
        (ProviderTypeMetadata, ProviderTypeMetadata.metadata_id),
        (AssetTypeProviderAssetMetadata, AssetTypeProviderAssetMetadata.metadata_id),
    ]:
        db.execute(model.__table__.delete().where(col == metadata_id))
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Attributes
# ---------------------------------------------------------------------------


def get_attributes(db: Session) -> list[Attribute]:
    return list(db.execute(select(Attribute)).scalars().all())


def get_attribute(db: Session, attribute_id: uuid.UUID) -> Attribute:
    obj = db.get(Attribute, attribute_id)
    if not obj:
        raise NotFoundError("Attribute not found")
    return obj


def create_attribute(db: Session, data: AttributeCreate) -> Attribute:
    existing = db.execute(select(Attribute).where(Attribute.name == data.name)).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Attribute with name '{data.name}' already exists")
    obj = Attribute(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_attribute(db: Session, attribute_id: uuid.UUID, data: AttributeUpdate) -> Attribute:
    obj = get_attribute(db, attribute_id)
    updates = data.model_dump(exclude_none=True)
    if "name" in updates and updates["name"] != obj.name:
        existing = db.execute(
            select(Attribute).where(Attribute.name == updates["name"])
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(f"Attribute with name '{updates['name']}' already exists")
    for key, val in updates.items():
        setattr(obj, key, val)
    db.commit()
    db.refresh(obj)
    return obj


def get_attribute_usage(db: Session, attribute_id: uuid.UUID) -> EntityUsage:
    get_attribute(db, attribute_id)
    return _build_usage(
        [
            (
                "Instrument Attributes",
                _count(
                    db,
                    InstrumentAttribute,
                    InstrumentAttribute.attribute_id,
                    attribute_id,
                ),
                "cascade",
            ),
            (
                "Instrument Period Attributes",
                _count(
                    db,
                    InstrumentPeriodAttribute,
                    InstrumentPeriodAttribute.attribute_id,
                    attribute_id,
                ),
                "cascade",
            ),
            (
                "Content Attributes",
                _count(
                    db,
                    ProviderContentAttribute,
                    ProviderContentAttribute.attribute_id,
                    attribute_id,
                ),
                "cascade",
            ),
        ]
    )


def delete_attribute(db: Session, attribute_id: uuid.UUID) -> None:
    obj = get_attribute(db, attribute_id)
    for model, col in [
        (InstrumentAttribute, InstrumentAttribute.attribute_id),
        (InstrumentPeriodAttribute, InstrumentPeriodAttribute.attribute_id),
        (ProviderContentAttribute, ProviderContentAttribute.attribute_id),
    ]:
        db.execute(model.__table__.delete().where(col == attribute_id))
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Asset Type usage + delete
# ---------------------------------------------------------------------------


def get_asset_type_usage(db: Session, asset_type_id: uuid.UUID) -> EntityUsage:
    obj = db.get(AssetType, asset_type_id)
    if not obj:
        raise NotFoundError("Asset type not found")

    asset_ids = _get_asset_ids_for_type(db, asset_type_id)
    asset_count = len(asset_ids)

    items: list[tuple[str, int, str]] = [
        ("Assets", asset_count, "cascade"),
        (
            "Child Types",
            _count(db, AssetType, AssetType.parent_type_id, asset_type_id),
            "reference",
        ),
        (
            "Metadata Field Definitions",
            _count(db, AssetTypeMetadata, AssetTypeMetadata.asset_type_id, asset_type_id),
            "cascade",
        ),
        (
            "Provider-Asset Field Definitions",
            _count(
                db,
                AssetTypeProviderAssetMetadata,
                AssetTypeProviderAssetMetadata.asset_type_id,
                asset_type_id,
            ),
            "cascade",
        ),
    ]
    # Add transitive counts from assets that would be deleted
    items.extend(_count_asset_cascade(db, asset_ids))

    return _build_usage(items)


def delete_asset_type(db: Session, asset_type_id: uuid.UUID) -> None:
    obj = db.get(AssetType, asset_type_id)
    if not obj:
        raise NotFoundError("Asset type not found")
    # Block only on child types (must delete children first to avoid orphans)
    child_count = _count(db, AssetType, AssetType.parent_type_id, asset_type_id)
    if child_count > 0:
        raise BadRequestError(
            "Cannot delete asset type with child types. Delete child types first."
        )

    # Cascade delete all assets of this type and their data
    asset_ids = _get_asset_ids_for_type(db, asset_type_id)
    _delete_assets_cascade(db, asset_ids)

    # Clean up type-level junction tables
    db.execute(
        AssetTypeMetadata.__table__.delete().where(AssetTypeMetadata.asset_type_id == asset_type_id)
    )
    db.execute(
        AssetTypeProviderAssetMetadata.__table__.delete().where(
            AssetTypeProviderAssetMetadata.asset_type_id == asset_type_id
        )
    )
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Provider Type usage + delete
# ---------------------------------------------------------------------------


def get_provider_type_usage(db: Session, provider_type_id: uuid.UUID) -> EntityUsage:
    obj = db.get(ProviderType, provider_type_id)
    if not obj:
        raise NotFoundError("Provider type not found")

    provider_ids = _get_provider_ids_for_type(db, provider_type_id)
    provider_count = len(provider_ids)

    items: list[tuple[str, int, str]] = [
        ("Providers", provider_count, "cascade"),
        (
            "Child Types",
            _count(db, ProviderType, ProviderType.parent_type_id, provider_type_id),
            "reference",
        ),
        (
            "Metadata Field Definitions",
            _count(
                db, ProviderTypeMetadata, ProviderTypeMetadata.provider_type_id, provider_type_id
            ),
            "cascade",
        ),
    ]
    # Add transitive counts from providers that would be deleted
    items.extend(_count_provider_cascade(db, provider_ids))

    return _build_usage(items)


def delete_provider_type(db: Session, provider_type_id: uuid.UUID) -> None:
    obj = db.get(ProviderType, provider_type_id)
    if not obj:
        raise NotFoundError("Provider type not found")
    # Block only on child types
    child_count = _count(db, ProviderType, ProviderType.parent_type_id, provider_type_id)
    if child_count > 0:
        raise BadRequestError(
            "Cannot delete provider type with child types. Delete child types first."
        )

    # Cascade delete all providers of this type and their data
    provider_ids = _get_provider_ids_for_type(db, provider_type_id)
    _delete_providers_cascade(db, provider_ids)

    # Clean up type-level junction tables
    db.execute(
        ProviderTypeMetadata.__table__.delete().where(
            ProviderTypeMetadata.provider_type_id == provider_type_id
        )
    )
    db.delete(obj)
    db.commit()


# ---------------------------------------------------------------------------
# Asset usage + cascade helpers
# ---------------------------------------------------------------------------


def get_asset_usage(db: Session, asset_id: uuid.UUID) -> EntityUsage:
    obj = db.get(Asset, asset_id)
    if not obj:
        raise NotFoundError("Asset not found")

    items: list[tuple[str, int, str]] = _count_asset_cascade(db, [asset_id])
    items.append(
        ("Underlying Assets", _count(db, Asset, Asset.underlying_asset_id, asset_id), "reference")
    )

    return _build_usage(items)


# ---------------------------------------------------------------------------
# Provider usage
# ---------------------------------------------------------------------------


def get_provider_usage(db: Session, provider_id: uuid.UUID) -> EntityUsage:
    obj = db.get(Provider, provider_id)
    if not obj:
        raise NotFoundError("Provider not found")

    items: list[tuple[str, int, str]] = _count_provider_cascade(db, [provider_id])
    items.append(
        (
            "Underlying Providers",
            _count(db, Provider, Provider.underlying_provider_id, provider_id),
            "reference",
        )
    )

    return _build_usage(items)


# ---------------------------------------------------------------------------
# Instrument usage
# ---------------------------------------------------------------------------


def get_instrument_usage(db: Session, instrument_id: uuid.UUID) -> EntityUsage:
    obj = db.get(Instrument, instrument_id)
    if not obj:
        raise NotFoundError("Instrument not found")

    items: list[tuple[str, int, str]] = [
        # Cascade — deleted with the instrument
        (
            "Instrument Metadata",
            _count(db, InstrumentMetadata, InstrumentMetadata.instrument_id, instrument_id),
            "cascade",
        ),
        (
            "Instrument Attributes",
            _count(db, InstrumentAttribute, InstrumentAttribute.instrument_id, instrument_id),
            "cascade",
        ),
        (
            "Instrument Period Attributes",
            _count(
                db,
                InstrumentPeriodAttribute,
                InstrumentPeriodAttribute.instrument_id,
                instrument_id,
            ),
            "cascade",
        ),
        # References — entities that use this instrument
        (
            "Composite Members",
            _count(db, CompositeMember, CompositeMember.instrument_id, instrument_id),
            "reference",
        ),
        (
            "Feed Scopes",
            _count(db, FeedInstrumentScope, FeedInstrumentScope.instrument_id, instrument_id),
            "reference",
        ),
        (
            "Strategy Scopes",
            _count(
                db, StrategyInstrumentScope, StrategyInstrumentScope.instrument_id, instrument_id
            ),
            "reference",
        ),
        ("Orders", _count(db, Order, Order.instrument_id, instrument_id), "reference"),
        ("Trade Legs", _count(db, TradeLeg, TradeLeg.instrument_id, instrument_id), "reference"),
    ]

    return _build_usage(items)


# ---------------------------------------------------------------------------
# Composite usage
# ---------------------------------------------------------------------------


def get_composite_usage(db: Session, composite_id: uuid.UUID) -> EntityUsage:
    obj = db.get(Composite, composite_id)
    if not obj:
        raise NotFoundError("Composite not found")

    items: list[tuple[str, int, str]] = [
        # Cascade — deleted with the composite
        (
            "Members",
            _count(db, CompositeMember, CompositeMember.composite_id, composite_id),
            "cascade",
        ),
        (
            "Composite Metadata",
            _count(db, CompositeMetadata, CompositeMetadata.composite_id, composite_id),
            "cascade",
        ),
        (
            "Composite Attributes",
            _count(db, CompositeAttribute, CompositeAttribute.composite_id, composite_id),
            "cascade",
        ),
        (
            "Composite Period Attributes",
            _count(
                db,
                CompositePeriodAttribute,
                CompositePeriodAttribute.composite_id,
                composite_id,
            ),
            "cascade",
        ),
        # References
        (
            "Feed Scopes",
            _count(db, FeedCompositeScope, FeedCompositeScope.composite_id, composite_id),
            "reference",
        ),
        (
            "Strategy Scopes",
            _count(db, StrategyCompositeScope, StrategyCompositeScope.composite_id, composite_id),
            "reference",
        ),
    ]

    return _build_usage(items)
