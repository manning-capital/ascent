import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models.asset_type_metadata import AssetTypeMetadata
from ascent.database.models.asset_type_provider_asset_metadata import AssetTypeProviderAssetMetadata
from ascent.database.models.instrument_type_metadata import InstrumentTypeMetadata
from ascent.database.models.provider_type_metadata import ProviderTypeMetadata
from ascent.database.models.types import AssetType, InstrumentType, ProviderType
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.metadata import (
    AssetTypeMetadataSchema,
    AssetTypeProviderAssetMetadataSchema,
    InstrumentTypeMetadataSchema,
    ProviderTypeMetadataSchema,
)
from ascent.server.schemas.types import (
    MetadataConflict,
    ReparentPreview,
    TypeHierarchyItem,
    TypeUpdate,
)


def get_type_ancestors(
    db: Session,
    model_class: type[AssetType] | type[InstrumentType] | type[ProviderType],
    type_id: uuid.UUID,
) -> list:
    """Walk up the parent chain, returning ancestors from immediate parent to root."""
    ancestors: list = []
    seen: set[uuid.UUID] = {type_id}
    current_id = type_id

    while True:
        row = db.get(model_class, current_id)
        if not row or row.parent_type_id is None:
            break
        if row.parent_type_id in seen:
            raise BadRequestError("Cycle detected in type hierarchy")
        seen.add(row.parent_type_id)
        parent = db.get(model_class, row.parent_type_id)
        if not parent:
            break
        ancestors.append(parent)
        current_id = row.parent_type_id

    return ancestors


def validate_parent_type(
    db: Session,
    model_class: type[AssetType] | type[InstrumentType] | type[ProviderType],
    type_id: uuid.UUID,
    proposed_parent_id: uuid.UUID,
) -> None:
    """Validate that setting parent_type_id won't create a cycle."""
    if type_id == proposed_parent_id:
        raise BadRequestError("A type cannot be its own parent")

    parent = db.get(model_class, proposed_parent_id)
    if not parent:
        raise NotFoundError("Parent type not found")

    # Walk up from proposed parent to ensure we never encounter type_id
    current_id = proposed_parent_id
    seen: set[uuid.UUID] = {type_id}
    while True:
        row = db.get(model_class, current_id)
        if not row or row.parent_type_id is None:
            break
        if row.parent_type_id in seen:
            raise BadRequestError("Setting this parent would create a cycle in the type hierarchy")
        seen.add(row.parent_type_id)
        current_id = row.parent_type_id


def get_effective_asset_type_metadata(
    db: Session,
    type_id: uuid.UUID,
) -> list[AssetTypeMetadataSchema]:
    """Get effective metadata fields: own fields + inherited from ancestors.

    Child fields take precedence over parent fields when the same metadata_id exists.
    """
    asset_type = db.get(AssetType, type_id)
    if not asset_type:
        raise NotFoundError("Asset type not found")

    ancestors = get_type_ancestors(db, AssetType, type_id)

    # Collect fields from most distant ancestor to self (so child overrides parent)
    fields_by_metadata_id: dict[uuid.UUID, AssetTypeMetadataSchema] = {}

    for ancestor in reversed(ancestors):
        rows = (
            db.execute(
                select(AssetTypeMetadata).where(AssetTypeMetadata.asset_type_id == ancestor.id)
            )
            .scalars()
            .all()
        )
        for r in rows:
            fields_by_metadata_id[r.metadata_id] = AssetTypeMetadataSchema(
                metadata_id=r.metadata_id,
                metadata_name=r.metadata_type.name if r.metadata_type else "",
                metadata_display_name=r.metadata_type.display_name if r.metadata_type else None,
                metadata_description=r.metadata_type.description if r.metadata_type else None,
                value_type=r.metadata_type.value_type if r.metadata_type else "string",
                config=r.metadata_type.config if r.metadata_type else None,
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.display_name,
            )

    # Own fields (override inherited if same metadata_id)
    own_rows = (
        db.execute(select(AssetTypeMetadata).where(AssetTypeMetadata.asset_type_id == type_id))
        .scalars()
        .all()
    )
    for r in own_rows:
        fields_by_metadata_id[r.metadata_id] = AssetTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
            source_type_id=None,
            source_type_name=None,
        )

    result = list(fields_by_metadata_id.values())
    result.sort(key=lambda f: (f.is_inherited, f.display_order))
    return result


def get_effective_provider_type_metadata(
    db: Session,
    type_id: uuid.UUID,
) -> list[ProviderTypeMetadataSchema]:
    """Get effective metadata fields for a provider type, including inherited."""
    provider_type = db.get(ProviderType, type_id)
    if not provider_type:
        raise NotFoundError("Provider type not found")

    ancestors = get_type_ancestors(db, ProviderType, type_id)

    fields_by_metadata_id: dict[uuid.UUID, ProviderTypeMetadataSchema] = {}

    for ancestor in reversed(ancestors):
        rows = (
            db.execute(
                select(ProviderTypeMetadata).where(
                    ProviderTypeMetadata.provider_type_id == ancestor.id
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            fields_by_metadata_id[r.metadata_id] = ProviderTypeMetadataSchema(
                metadata_id=r.metadata_id,
                metadata_name=r.metadata_type.name if r.metadata_type else "",
                metadata_display_name=r.metadata_type.display_name if r.metadata_type else None,
                metadata_description=r.metadata_type.description if r.metadata_type else None,
                value_type=r.metadata_type.value_type if r.metadata_type else "string",
                config=r.metadata_type.config if r.metadata_type else None,
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.display_name,
            )

    own_rows = (
        db.execute(
            select(ProviderTypeMetadata).where(ProviderTypeMetadata.provider_type_id == type_id)
        )
        .scalars()
        .all()
    )
    for r in own_rows:
        fields_by_metadata_id[r.metadata_id] = ProviderTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
            source_type_id=None,
            source_type_name=None,
        )

    result = list(fields_by_metadata_id.values())
    result.sort(key=lambda f: (f.is_inherited, f.display_order))
    return result


def get_effective_asset_type_provider_asset_metadata(
    db: Session,
    type_id: uuid.UUID,
) -> list[AssetTypeProviderAssetMetadataSchema]:
    """Get effective provider-asset metadata fields for an asset type, including inherited."""
    asset_type = db.get(AssetType, type_id)
    if not asset_type:
        raise NotFoundError("Asset type not found")

    ancestors = get_type_ancestors(db, AssetType, type_id)

    fields_by_metadata_id: dict[uuid.UUID, AssetTypeProviderAssetMetadataSchema] = {}

    for ancestor in reversed(ancestors):
        rows = (
            db.execute(
                select(AssetTypeProviderAssetMetadata).where(
                    AssetTypeProviderAssetMetadata.asset_type_id == ancestor.id
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            fields_by_metadata_id[r.metadata_id] = AssetTypeProviderAssetMetadataSchema(
                metadata_id=r.metadata_id,
                metadata_name=r.metadata_type.name if r.metadata_type else "",
                metadata_display_name=r.metadata_type.display_name if r.metadata_type else None,
                metadata_description=r.metadata_type.description if r.metadata_type else None,
                value_type=r.metadata_type.value_type if r.metadata_type else "string",
                config=r.metadata_type.config if r.metadata_type else None,
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.display_name,
            )

    own_rows = (
        db.execute(
            select(AssetTypeProviderAssetMetadata).where(
                AssetTypeProviderAssetMetadata.asset_type_id == type_id
            )
        )
        .scalars()
        .all()
    )
    for r in own_rows:
        fields_by_metadata_id[r.metadata_id] = AssetTypeProviderAssetMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
            source_type_id=None,
            source_type_name=None,
        )

    result = list(fields_by_metadata_id.values())
    result.sort(key=lambda f: (f.is_inherited, f.display_order))
    return result


def build_type_tree(
    db: Session,
    model_class: type[AssetType] | type[InstrumentType] | type[ProviderType],
) -> list[TypeHierarchyItem]:
    """Load all types and build a tree structure."""
    all_types = db.execute(select(model_class)).scalars().all()

    nodes: dict[uuid.UUID, TypeHierarchyItem] = {}
    for t in all_types:
        nodes[t.id] = TypeHierarchyItem(
            id=t.id,
            name=t.name,
            display_name=t.display_name,
            description=t.description,
            parent_type_id=t.parent_type_id,
            children=[],
        )

    roots: list[TypeHierarchyItem] = []
    for node in nodes.values():
        if node.parent_type_id and node.parent_type_id in nodes:
            nodes[node.parent_type_id].children.append(node)
        else:
            roots.append(node)

    return roots


def _get_own_asset_type_metadata(db: Session, type_id: uuid.UUID) -> list[AssetTypeMetadataSchema]:
    rows = (
        db.execute(select(AssetTypeMetadata).where(AssetTypeMetadata.asset_type_id == type_id))
        .scalars()
        .all()
    )
    return [
        AssetTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
        )
        for r in rows
    ]


def _get_own_asset_type_provider_asset_metadata(
    db: Session, type_id: uuid.UUID
) -> list[AssetTypeProviderAssetMetadataSchema]:
    rows = (
        db.execute(
            select(AssetTypeProviderAssetMetadata).where(
                AssetTypeProviderAssetMetadata.asset_type_id == type_id
            )
        )
        .scalars()
        .all()
    )
    return [
        AssetTypeProviderAssetMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
        )
        for r in rows
    ]


def _get_own_provider_type_metadata(
    db: Session, type_id: uuid.UUID
) -> list[ProviderTypeMetadataSchema]:
    rows = (
        db.execute(
            select(ProviderTypeMetadata).where(ProviderTypeMetadata.provider_type_id == type_id)
        )
        .scalars()
        .all()
    )
    return [
        ProviderTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
        )
        for r in rows
    ]


def _compute_conflicts(child_fields, parent_fields) -> list[MetadataConflict]:
    parent_by_id = {f.metadata_id: f for f in parent_fields}
    conflicts = []
    for cf in child_fields:
        pf = parent_by_id.get(cf.metadata_id)
        if pf:
            conflicts.append(
                MetadataConflict(
                    metadata_id=cf.metadata_id,
                    metadata_name=cf.metadata_name,
                    metadata_display_name=getattr(cf, "metadata_display_name", cf.metadata_name),
                    value_type=cf.value_type,
                    child_is_required=cf.is_required,
                    parent_is_required=pf.is_required,
                    parent_source_type_name=pf.source_type_name or "Parent",
                )
            )
    return conflicts


def preview_asset_type_reparent(
    db: Session, child_id: uuid.UUID, new_parent_id: uuid.UUID
) -> ReparentPreview:
    child = db.get(AssetType, child_id)
    if not child:
        raise NotFoundError("Asset type not found")
    parent = db.get(AssetType, new_parent_id)
    if not parent:
        raise NotFoundError("Parent asset type not found")
    validate_parent_type(db, AssetType, child.id, new_parent_id)

    child_own = _get_own_asset_type_metadata(db, child_id)
    parent_effective = get_effective_asset_type_metadata(db, new_parent_id)
    conflicts = _compute_conflicts(child_own, parent_effective)

    child_own_pa = _get_own_asset_type_provider_asset_metadata(db, child_id)
    parent_effective_pa = get_effective_asset_type_provider_asset_metadata(db, new_parent_id)
    pa_conflicts = _compute_conflicts(child_own_pa, parent_effective_pa)

    return ReparentPreview(
        child_id=child.id,
        child_name=child.display_name,
        new_parent_id=parent.id,
        new_parent_name=parent.display_name,
        child_own_fields=[f.model_dump() for f in child_own],
        parent_effective_fields=[f.model_dump() for f in parent_effective],
        conflicts=conflicts,
        child_own_provider_asset_fields=[f.model_dump() for f in child_own_pa],
        parent_effective_provider_asset_fields=[f.model_dump() for f in parent_effective_pa],
        provider_asset_conflicts=pa_conflicts,
    )


def preview_provider_type_reparent(
    db: Session, child_id: uuid.UUID, new_parent_id: uuid.UUID
) -> ReparentPreview:
    child = db.get(ProviderType, child_id)
    if not child:
        raise NotFoundError("Provider type not found")
    parent = db.get(ProviderType, new_parent_id)
    if not parent:
        raise NotFoundError("Parent provider type not found")
    validate_parent_type(db, ProviderType, child.id, new_parent_id)

    child_own = _get_own_provider_type_metadata(db, child_id)
    parent_effective = get_effective_provider_type_metadata(db, new_parent_id)
    conflicts = _compute_conflicts(child_own, parent_effective)

    return ReparentPreview(
        child_id=child.id,
        child_name=child.display_name,
        new_parent_id=parent.id,
        new_parent_name=parent.display_name,
        child_own_fields=[f.model_dump() for f in child_own],
        parent_effective_fields=[f.model_dump() for f in parent_effective],
        conflicts=conflicts,
    )


def execute_asset_type_reparent(db: Session, child_id: uuid.UUID, data: TypeUpdate) -> None:
    for mid in data.remove_metadata_ids:
        obj = db.execute(
            select(AssetTypeMetadata).where(
                AssetTypeMetadata.asset_type_id == child_id,
                AssetTypeMetadata.metadata_id == mid,
            )
        ).scalar_one_or_none()
        if obj:
            db.delete(obj)

    for mid in data.remove_provider_asset_metadata_ids:
        obj = db.execute(
            select(AssetTypeProviderAssetMetadata).where(
                AssetTypeProviderAssetMetadata.asset_type_id == child_id,
                AssetTypeProviderAssetMetadata.metadata_id == mid,
            )
        ).scalar_one_or_none()
        if obj:
            db.delete(obj)


def execute_provider_type_reparent(db: Session, child_id: uuid.UUID, data: TypeUpdate) -> None:
    for mid in data.remove_metadata_ids:
        obj = db.execute(
            select(ProviderTypeMetadata).where(
                ProviderTypeMetadata.provider_type_id == child_id,
                ProviderTypeMetadata.metadata_id == mid,
            )
        ).scalar_one_or_none()
        if obj:
            db.delete(obj)


def get_effective_instrument_type_metadata(
    db: Session,
    type_id: uuid.UUID,
) -> list[InstrumentTypeMetadataSchema]:
    """Get effective metadata fields for an instrument type, including inherited."""
    instrument_type = db.get(InstrumentType, type_id)
    if not instrument_type:
        raise NotFoundError("Instrument type not found")

    ancestors = get_type_ancestors(db, InstrumentType, type_id)

    fields_by_metadata_id: dict[uuid.UUID, InstrumentTypeMetadataSchema] = {}

    for ancestor in reversed(ancestors):
        rows = (
            db.execute(
                select(InstrumentTypeMetadata).where(
                    InstrumentTypeMetadata.instrument_type_id == ancestor.id
                )
            )
            .scalars()
            .all()
        )
        for r in rows:
            fields_by_metadata_id[r.metadata_id] = InstrumentTypeMetadataSchema(
                metadata_id=r.metadata_id,
                metadata_name=r.metadata_type.name if r.metadata_type else "",
                metadata_display_name=r.metadata_type.display_name if r.metadata_type else None,
                metadata_description=r.metadata_type.description if r.metadata_type else None,
                value_type=r.metadata_type.value_type if r.metadata_type else "string",
                config=r.metadata_type.config if r.metadata_type else None,
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.display_name,
            )

    own_rows = (
        db.execute(
            select(InstrumentTypeMetadata).where(
                InstrumentTypeMetadata.instrument_type_id == type_id
            )
        )
        .scalars()
        .all()
    )
    for r in own_rows:
        fields_by_metadata_id[r.metadata_id] = InstrumentTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
            source_type_id=None,
            source_type_name=None,
        )

    result = list(fields_by_metadata_id.values())
    result.sort(key=lambda f: (f.is_inherited, f.display_order))
    return result


def _get_own_instrument_type_metadata(
    db: Session, type_id: uuid.UUID
) -> list[InstrumentTypeMetadataSchema]:
    rows = (
        db.execute(
            select(InstrumentTypeMetadata).where(
                InstrumentTypeMetadata.instrument_type_id == type_id
            )
        )
        .scalars()
        .all()
    )
    return [
        InstrumentTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name if r.metadata_type else "",
            metadata_display_name=r.metadata_type.display_name if r.metadata_type else "",
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
            config=r.metadata_type.config if r.metadata_type else None,
            is_required=r.is_required,
            display_order=r.display_order,
            is_inherited=False,
        )
        for r in rows
    ]


def preview_instrument_type_reparent(
    db: Session, child_id: uuid.UUID, new_parent_id: uuid.UUID
) -> ReparentPreview:
    child = db.get(InstrumentType, child_id)
    if not child:
        raise NotFoundError("Instrument type not found")
    parent = db.get(InstrumentType, new_parent_id)
    if not parent:
        raise NotFoundError("Parent instrument type not found")
    validate_parent_type(db, InstrumentType, child.id, new_parent_id)

    child_own = _get_own_instrument_type_metadata(db, child_id)
    parent_effective = get_effective_instrument_type_metadata(db, new_parent_id)
    conflicts = _compute_conflicts(child_own, parent_effective)

    return ReparentPreview(
        child_id=child.id,
        child_name=child.display_name,
        new_parent_id=parent.id,
        new_parent_name=parent.display_name,
        child_own_fields=[f.model_dump() for f in child_own],
        parent_effective_fields=[f.model_dump() for f in parent_effective],
        conflicts=conflicts,
    )


def execute_instrument_type_reparent(db: Session, child_id: uuid.UUID, data: TypeUpdate) -> None:
    for mid in data.remove_metadata_ids:
        obj = db.execute(
            select(InstrumentTypeMetadata).where(
                InstrumentTypeMetadata.instrument_type_id == child_id,
                InstrumentTypeMetadata.metadata_id == mid,
            )
        ).scalar_one_or_none()
        if obj:
            db.delete(obj)
