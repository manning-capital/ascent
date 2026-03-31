from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import (
    AssetType,
    AssetTypeMetadata,
    AssetTypeProviderAssetMetadata,
    CompositeType,
    ExchangeType,
    FeedType,
    InstrumentType,
    Metadata,
    OrderStatusType,
    OrderType,
    ProviderType,
    ProviderTypeMetadata,
    StrategyType,
    TradeStatusType,
    TransactionStatusType,
    TransactionType,
)
from ascent.database.models.composite_type_metadata import CompositeTypeMetadata
from ascent.database.models.instrument_type_metadata import InstrumentTypeMetadata
from ascent.server.dependencies import get_db
from ascent.server.exceptions import ConflictError, NotFoundError
from ascent.server.schemas.metadata import (
    AssetTypeMetadataCreate,
    AssetTypeMetadataSchema,
    AssetTypeProviderAssetMetadataCreate,
    AssetTypeProviderAssetMetadataSchema,
    CompositeTypeMetadataCreate,
    CompositeTypeMetadataSchema,
    EntityUsage,
    InstrumentTypeMetadataCreate,
    InstrumentTypeMetadataSchema,
    MetadataTypeCreate,
    MetadataTypeSchema,
    MetadataTypeUpdate,
    ProviderTypeMetadataCreate,
    ProviderTypeMetadataSchema,
)
from ascent.server.schemas.types import (
    CompositeTypeCreate,
    CompositeTypeHierarchyItem,
    CompositeTypeItem,
    CompositeTypePatch,
    InstrumentTypeCreate,
    InstrumentTypeHierarchyItem,
    InstrumentTypeItem,
    ReparentPreview,
    TypeCreate,
    TypeHierarchyItem,
    TypeItem,
    TypePatch,
    TypeUpdate,
)
from ascent.server.services import field_service
from ascent.server.services.type_service import (
    build_type_tree,
    execute_asset_type_reparent,
    execute_instrument_type_reparent,
    execute_provider_type_reparent,
    get_effective_asset_type_metadata,
    get_effective_asset_type_provider_asset_metadata,
    get_effective_instrument_type_metadata,
    get_effective_provider_type_metadata,
    preview_asset_type_reparent,
    preview_instrument_type_reparent,
    preview_provider_type_reparent,
    validate_parent_type,
)

router = APIRouter(prefix="/types", tags=["types"])


def _create_type(db: Session, model_class, data: TypeCreate):
    dump = data.model_dump(exclude_none=True)
    obj = model_class(**dump)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/metadata-types", response_model=list[MetadataTypeSchema])
def list_metadata_types(db: Session = Depends(get_db)):
    return [MetadataTypeSchema.model_validate(r) for r in field_service.get_metadata_types(db)]


@router.post("/metadata-types", status_code=201, response_model=MetadataTypeSchema)
def create_metadata_type(data: MetadataTypeCreate, db: Session = Depends(get_db)):
    return MetadataTypeSchema.model_validate(field_service.create_metadata_type(db, data))


@router.get("/metadata-types/{metadata_type_id}", response_model=MetadataTypeSchema)
def get_metadata_type(metadata_type_id: str, db: Session = Depends(get_db)):
    return MetadataTypeSchema.model_validate(field_service.get_metadata_type(db, metadata_type_id))


@router.put("/metadata-types/{metadata_type_id}", response_model=MetadataTypeSchema)
def update_metadata_type(
    metadata_type_id: str, data: MetadataTypeUpdate, db: Session = Depends(get_db)
):
    return MetadataTypeSchema.model_validate(
        field_service.update_metadata_type(db, metadata_type_id, data)
    )


@router.get("/metadata-types/{metadata_type_id}/usage", response_model=EntityUsage)
def get_metadata_type_usage(metadata_type_id: str, db: Session = Depends(get_db)):
    return field_service.get_metadata_type_usage(db, metadata_type_id)


@router.delete("/metadata-types/{metadata_type_id}", status_code=204)
def delete_metadata_type(metadata_type_id: str, db: Session = Depends(get_db)):
    field_service.delete_metadata_type(db, metadata_type_id)


@router.get("/asset-types", response_model=list[TypeItem])
def list_asset_types(db: Session = Depends(get_db)):
    result = db.execute(select(AssetType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.get("/asset-types/tree", response_model=list[TypeHierarchyItem])
def get_asset_type_tree(db: Session = Depends(get_db)):
    return build_type_tree(db, AssetType)


@router.post("/asset-types", status_code=201)
def create_asset_type(data: TypeCreate, db: Session = Depends(get_db)):
    if data.parent_type_id:
        parent = db.get(AssetType, data.parent_type_id)
        if not parent:
            raise NotFoundError("Parent asset type not found")
    return _create_type(db, AssetType, data)


@router.put("/asset-types/{asset_type_id}", response_model=TypeItem)
def update_asset_type(asset_type_id: str, data: TypeUpdate, db: Session = Depends(get_db)):
    obj = db.get(AssetType, asset_type_id)
    if not obj:
        raise NotFoundError("Asset type not found")
    if data.parent_type_id is not None:
        validate_parent_type(db, AssetType, obj.id, data.parent_type_id)
    if data.remove_metadata_ids or data.remove_provider_asset_metadata_ids:
        execute_asset_type_reparent(db, obj.id, data)
    obj.parent_type_id = data.parent_type_id
    db.commit()
    db.refresh(obj)
    return TypeItem.model_validate(obj)


@router.patch("/asset-types/{asset_type_id}", response_model=TypeItem)
def patch_asset_type(asset_type_id: str, data: TypePatch, db: Session = Depends(get_db)):
    obj = db.get(AssetType, asset_type_id)
    if not obj:
        raise NotFoundError("Asset type not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return TypeItem.model_validate(obj)


@router.get("/asset-types/{asset_type_id}/reparent-preview", response_model=ReparentPreview)
def get_asset_type_reparent_preview(
    asset_type_id: str, new_parent_id: str = Query(), db: Session = Depends(get_db)
):
    return preview_asset_type_reparent(db, asset_type_id, new_parent_id)


@router.get("/asset-types/{asset_type_id}/usage", response_model=EntityUsage)
def get_asset_type_usage(asset_type_id: str, db: Session = Depends(get_db)):
    return field_service.get_asset_type_usage(db, asset_type_id)


@router.delete("/asset-types/{asset_type_id}", status_code=204)
def delete_asset_type(asset_type_id: str, db: Session = Depends(get_db)):
    field_service.delete_asset_type(db, asset_type_id)


# ---- Asset Type Metadata Requirements ----


@router.get("/asset-types/{asset_type_id}/metadata", response_model=list[AssetTypeMetadataSchema])
def list_asset_type_metadata(
    asset_type_id: str,
    include_inherited: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    if include_inherited:
        return get_effective_asset_type_metadata(db, asset_type_id)

    rows = (
        db.execute(
            select(AssetTypeMetadata)
            .where(AssetTypeMetadata.asset_type_id == asset_type_id)
            .order_by(AssetTypeMetadata.display_order)
        )
        .scalars()
        .all()
    )
    return [
        AssetTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name,
            metadata_display_name=r.metadata_type.display_name,
            metadata_description=r.metadata_type.description,
            value_type=r.metadata_type.value_type,
            is_required=r.is_required,
            display_order=r.display_order,
        )
        for r in rows
    ]


@router.post(
    "/asset-types/{asset_type_id}/metadata", status_code=201, response_model=AssetTypeMetadataSchema
)
def add_asset_type_metadata(
    asset_type_id: str, data: AssetTypeMetadataCreate, db: Session = Depends(get_db)
):
    existing = db.execute(
        select(AssetTypeMetadata).where(
            AssetTypeMetadata.asset_type_id == asset_type_id,
            AssetTypeMetadata.metadata_id == data.metadata_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("Metadata field already linked to this asset type")

    new_meta = db.get(Metadata, data.metadata_id)
    if not new_meta:
        raise NotFoundError("Metadata type not found")
    effective = get_effective_asset_type_metadata(db, asset_type_id)
    for f in effective:
        if f.metadata_name == new_meta.name:
            raise ConflictError(
                f"A field with the name '{new_meta.name}' already exists (inherited from '{f.source_type_name}')"
                if f.is_inherited
                else f"A field with the name '{new_meta.name}' already exists on this type"
            )

    obj = AssetTypeMetadata(
        asset_type_id=asset_type_id,
        metadata_id=data.metadata_id,
        is_required=data.is_required,
        display_order=data.display_order,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return AssetTypeMetadataSchema(
        metadata_id=obj.metadata_id,
        metadata_name=obj.metadata_type.name,
        metadata_display_name=obj.metadata_type.display_name,
        metadata_description=obj.metadata_type.description,
        value_type=obj.metadata_type.value_type,
        is_required=obj.is_required,
        display_order=obj.display_order,
    )


@router.delete("/asset-types/{asset_type_id}/metadata/{metadata_id}", status_code=204)
def remove_asset_type_metadata(asset_type_id: str, metadata_id: str, db: Session = Depends(get_db)):
    obj = db.execute(
        select(AssetTypeMetadata).where(
            AssetTypeMetadata.asset_type_id == asset_type_id,
            AssetTypeMetadata.metadata_id == metadata_id,
        )
    ).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Asset type metadata not found")
    db.delete(obj)
    db.commit()


# ---- Asset Type Provider-Asset Metadata Requirements ----


@router.get(
    "/asset-types/{asset_type_id}/provider-asset-metadata",
    response_model=list[AssetTypeProviderAssetMetadataSchema],
)
def list_asset_type_provider_asset_metadata(
    asset_type_id: str,
    include_inherited: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    if include_inherited:
        return get_effective_asset_type_provider_asset_metadata(db, asset_type_id)

    rows = (
        db.execute(
            select(AssetTypeProviderAssetMetadata)
            .where(AssetTypeProviderAssetMetadata.asset_type_id == asset_type_id)
            .order_by(AssetTypeProviderAssetMetadata.display_order)
        )
        .scalars()
        .all()
    )
    return [
        AssetTypeProviderAssetMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name,
            metadata_display_name=r.metadata_type.display_name,
            metadata_description=r.metadata_type.description,
            value_type=r.metadata_type.value_type,
            is_required=r.is_required,
            display_order=r.display_order,
        )
        for r in rows
    ]


@router.post(
    "/asset-types/{asset_type_id}/provider-asset-metadata",
    status_code=201,
    response_model=AssetTypeProviderAssetMetadataSchema,
)
def add_asset_type_provider_asset_metadata(
    asset_type_id: str,
    data: AssetTypeProviderAssetMetadataCreate,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(AssetTypeProviderAssetMetadata).where(
            AssetTypeProviderAssetMetadata.asset_type_id == asset_type_id,
            AssetTypeProviderAssetMetadata.metadata_id == data.metadata_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError(
            "Metadata field already linked to this asset type's provider-asset schema"
        )

    new_meta = db.get(Metadata, data.metadata_id)
    if not new_meta:
        raise NotFoundError("Metadata type not found")
    effective = get_effective_asset_type_provider_asset_metadata(db, asset_type_id)
    for f in effective:
        if f.metadata_name == new_meta.name:
            raise ConflictError(
                f"A provider-asset field with the name '{new_meta.name}' already exists (inherited from '{f.source_type_name}')"
                if f.is_inherited
                else f"A provider-asset field with the name '{new_meta.name}' already exists on this type"
            )

    obj = AssetTypeProviderAssetMetadata(
        asset_type_id=asset_type_id,
        metadata_id=data.metadata_id,
        is_required=data.is_required,
        display_order=data.display_order,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return AssetTypeProviderAssetMetadataSchema(
        metadata_id=obj.metadata_id,
        metadata_name=obj.metadata_type.name,
        metadata_display_name=obj.metadata_type.display_name,
        metadata_description=obj.metadata_type.description,
        value_type=obj.metadata_type.value_type,
        is_required=obj.is_required,
        display_order=obj.display_order,
    )


@router.delete(
    "/asset-types/{asset_type_id}/provider-asset-metadata/{metadata_id}", status_code=204
)
def remove_asset_type_provider_asset_metadata(
    asset_type_id: str, metadata_id: str, db: Session = Depends(get_db)
):
    obj = db.execute(
        select(AssetTypeProviderAssetMetadata).where(
            AssetTypeProviderAssetMetadata.asset_type_id == asset_type_id,
            AssetTypeProviderAssetMetadata.metadata_id == metadata_id,
        )
    ).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Asset type provider-asset metadata not found")
    db.delete(obj)
    db.commit()


# ---- Other type endpoints ----


@router.get("/provider-types", response_model=list[TypeItem])
def list_provider_types(db: Session = Depends(get_db)):
    result = db.execute(select(ProviderType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.get("/provider-types/tree", response_model=list[TypeHierarchyItem])
def get_provider_type_tree(db: Session = Depends(get_db)):
    return build_type_tree(db, ProviderType)


@router.post("/provider-types", status_code=201)
def create_provider_type(data: TypeCreate, db: Session = Depends(get_db)):
    if data.parent_type_id:
        parent = db.get(ProviderType, data.parent_type_id)
        if not parent:
            raise NotFoundError("Parent provider type not found")
    return _create_type(db, ProviderType, data)


@router.put("/provider-types/{provider_type_id}", response_model=TypeItem)
def update_provider_type(provider_type_id: str, data: TypeUpdate, db: Session = Depends(get_db)):
    obj = db.get(ProviderType, provider_type_id)
    if not obj:
        raise NotFoundError("Provider type not found")
    if data.parent_type_id is not None:
        validate_parent_type(db, ProviderType, obj.id, data.parent_type_id)
    if data.remove_metadata_ids:
        execute_provider_type_reparent(db, obj.id, data)
    obj.parent_type_id = data.parent_type_id
    db.commit()
    db.refresh(obj)
    return TypeItem.model_validate(obj)


@router.patch("/provider-types/{provider_type_id}", response_model=TypeItem)
def patch_provider_type(provider_type_id: str, data: TypePatch, db: Session = Depends(get_db)):
    obj = db.get(ProviderType, provider_type_id)
    if not obj:
        raise NotFoundError("Provider type not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return TypeItem.model_validate(obj)


@router.get("/provider-types/{provider_type_id}/reparent-preview", response_model=ReparentPreview)
def get_provider_type_reparent_preview(
    provider_type_id: str, new_parent_id: str = Query(), db: Session = Depends(get_db)
):
    return preview_provider_type_reparent(db, provider_type_id, new_parent_id)


@router.get("/provider-types/{provider_type_id}/usage", response_model=EntityUsage)
def get_provider_type_usage(provider_type_id: str, db: Session = Depends(get_db)):
    return field_service.get_provider_type_usage(db, provider_type_id)


@router.delete("/provider-types/{provider_type_id}", status_code=204)
def delete_provider_type(provider_type_id: str, db: Session = Depends(get_db)):
    field_service.delete_provider_type(db, provider_type_id)


# ---- Provider Type Metadata Requirements ----


@router.get(
    "/provider-types/{provider_type_id}/metadata", response_model=list[ProviderTypeMetadataSchema]
)
def list_provider_type_metadata(
    provider_type_id: str,
    include_inherited: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    if include_inherited:
        return get_effective_provider_type_metadata(db, provider_type_id)

    rows = (
        db.execute(
            select(ProviderTypeMetadata)
            .where(ProviderTypeMetadata.provider_type_id == provider_type_id)
            .order_by(ProviderTypeMetadata.display_order)
        )
        .scalars()
        .all()
    )
    return [
        ProviderTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name,
            metadata_display_name=r.metadata_type.display_name,
            metadata_description=r.metadata_type.description,
            value_type=r.metadata_type.value_type,
            is_required=r.is_required,
            display_order=r.display_order,
        )
        for r in rows
    ]


@router.post(
    "/provider-types/{provider_type_id}/metadata",
    status_code=201,
    response_model=ProviderTypeMetadataSchema,
)
def add_provider_type_metadata(
    provider_type_id: str, data: ProviderTypeMetadataCreate, db: Session = Depends(get_db)
):
    existing = db.execute(
        select(ProviderTypeMetadata).where(
            ProviderTypeMetadata.provider_type_id == provider_type_id,
            ProviderTypeMetadata.metadata_id == data.metadata_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("Metadata field already linked to this provider type")

    new_meta = db.get(Metadata, data.metadata_id)
    if not new_meta:
        raise NotFoundError("Metadata type not found")
    effective = get_effective_provider_type_metadata(db, provider_type_id)
    for f in effective:
        if f.metadata_name == new_meta.name:
            raise ConflictError(
                f"A field with the name '{new_meta.name}' already exists (inherited from '{f.source_type_name}')"
                if f.is_inherited
                else f"A field with the name '{new_meta.name}' already exists on this type"
            )

    obj = ProviderTypeMetadata(
        provider_type_id=provider_type_id,
        metadata_id=data.metadata_id,
        is_required=data.is_required,
        display_order=data.display_order,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return ProviderTypeMetadataSchema(
        metadata_id=obj.metadata_id,
        metadata_name=obj.metadata_type.name,
        metadata_display_name=obj.metadata_type.display_name,
        metadata_description=obj.metadata_type.description,
        value_type=obj.metadata_type.value_type,
        is_required=obj.is_required,
        display_order=obj.display_order,
    )


@router.delete("/provider-types/{provider_type_id}/metadata/{metadata_id}", status_code=204)
def remove_provider_type_metadata(
    provider_type_id: str, metadata_id: str, db: Session = Depends(get_db)
):
    obj = db.execute(
        select(ProviderTypeMetadata).where(
            ProviderTypeMetadata.provider_type_id == provider_type_id,
            ProviderTypeMetadata.metadata_id == metadata_id,
        )
    ).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Provider type metadata not found")
    db.delete(obj)
    db.commit()


# ---- Instrument Type endpoints ----


@router.get("/instrument-types", response_model=list[InstrumentTypeItem])
def list_instrument_types(db: Session = Depends(get_db)):
    result = db.execute(select(InstrumentType)).scalars().all()
    return [InstrumentTypeItem.model_validate(r) for r in result]


@router.get("/instrument-types/tree", response_model=list[InstrumentTypeHierarchyItem])
def get_instrument_type_tree(db: Session = Depends(get_db)):
    return build_type_tree(db, InstrumentType)


@router.post("/instrument-types", status_code=201, response_model=InstrumentTypeItem)
def create_instrument_type(data: InstrumentTypeCreate, db: Session = Depends(get_db)):
    if data.parent_type_id:
        parent = db.get(InstrumentType, data.parent_type_id)
        if not parent:
            raise NotFoundError("Parent instrument type not found")
    return _create_type(db, InstrumentType, data)


@router.put("/instrument-types/{instrument_type_id}", response_model=InstrumentTypeItem)
def update_instrument_type(
    instrument_type_id: str, data: TypeUpdate, db: Session = Depends(get_db)
):
    obj = db.get(InstrumentType, instrument_type_id)
    if not obj:
        raise NotFoundError("Instrument type not found")
    if data.parent_type_id is not None:
        validate_parent_type(db, InstrumentType, obj.id, data.parent_type_id)
    if data.remove_metadata_ids:
        execute_instrument_type_reparent(db, obj.id, data)
    obj.parent_type_id = data.parent_type_id
    db.commit()
    db.refresh(obj)
    return InstrumentTypeItem.model_validate(obj)


@router.patch("/instrument-types/{instrument_type_id}", response_model=InstrumentTypeItem)
def patch_instrument_type(instrument_type_id: str, data: TypePatch, db: Session = Depends(get_db)):
    obj = db.get(InstrumentType, instrument_type_id)
    if not obj:
        raise NotFoundError("Instrument type not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return InstrumentTypeItem.model_validate(obj)


@router.get(
    "/instrument-types/{instrument_type_id}/reparent-preview", response_model=ReparentPreview
)
def get_instrument_type_reparent_preview(
    instrument_type_id: str, new_parent_id: str = Query(), db: Session = Depends(get_db)
):
    return preview_instrument_type_reparent(db, instrument_type_id, new_parent_id)


@router.get("/instrument-types/{instrument_type_id}/usage", response_model=EntityUsage)
def get_instrument_type_usage(instrument_type_id: str, db: Session = Depends(get_db)):
    return EntityUsage(items=[], total=0)


@router.delete("/instrument-types/{instrument_type_id}", status_code=204)
def delete_instrument_type(instrument_type_id: str, db: Session = Depends(get_db)):
    obj = db.get(InstrumentType, instrument_type_id)
    if not obj:
        raise NotFoundError("Instrument type not found")
    db.delete(obj)
    db.commit()


# ---- Instrument Type Metadata Requirements ----


@router.get(
    "/instrument-types/{instrument_type_id}/metadata",
    response_model=list[InstrumentTypeMetadataSchema],
)
def list_instrument_type_metadata(
    instrument_type_id: str,
    include_inherited: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    if include_inherited:
        return get_effective_instrument_type_metadata(db, instrument_type_id)

    rows = (
        db.execute(
            select(InstrumentTypeMetadata)
            .where(InstrumentTypeMetadata.instrument_type_id == instrument_type_id)
            .order_by(InstrumentTypeMetadata.display_order)
        )
        .scalars()
        .all()
    )
    return [
        InstrumentTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name,
            metadata_display_name=r.metadata_type.display_name,
            metadata_description=r.metadata_type.description,
            value_type=r.metadata_type.value_type,
            is_required=r.is_required,
            display_order=r.display_order,
        )
        for r in rows
    ]


@router.post(
    "/instrument-types/{instrument_type_id}/metadata",
    status_code=201,
    response_model=InstrumentTypeMetadataSchema,
)
def add_instrument_type_metadata(
    instrument_type_id: str, data: InstrumentTypeMetadataCreate, db: Session = Depends(get_db)
):
    existing = db.execute(
        select(InstrumentTypeMetadata).where(
            InstrumentTypeMetadata.instrument_type_id == instrument_type_id,
            InstrumentTypeMetadata.metadata_id == data.metadata_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("Metadata field already linked to this instrument type")

    new_meta = db.get(Metadata, data.metadata_id)
    if not new_meta:
        raise NotFoundError("Metadata type not found")
    effective = get_effective_instrument_type_metadata(db, instrument_type_id)
    for f in effective:
        if f.metadata_name == new_meta.name:
            raise ConflictError(
                f"A field with the name '{new_meta.name}' already exists (inherited from '{f.source_type_name}')"
                if f.is_inherited
                else f"A field with the name '{new_meta.name}' already exists on this type"
            )

    obj = InstrumentTypeMetadata(
        instrument_type_id=instrument_type_id,
        metadata_id=data.metadata_id,
        is_required=data.is_required,
        display_order=data.display_order,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return InstrumentTypeMetadataSchema(
        metadata_id=obj.metadata_id,
        metadata_name=obj.metadata_type.name,
        metadata_display_name=obj.metadata_type.display_name,
        metadata_description=obj.metadata_type.description,
        value_type=obj.metadata_type.value_type,
        is_required=obj.is_required,
        display_order=obj.display_order,
    )


@router.delete("/instrument-types/{instrument_type_id}/metadata/{metadata_id}", status_code=204)
def remove_instrument_type_metadata(
    instrument_type_id: str, metadata_id: str, db: Session = Depends(get_db)
):
    obj = db.execute(
        select(InstrumentTypeMetadata).where(
            InstrumentTypeMetadata.instrument_type_id == instrument_type_id,
            InstrumentTypeMetadata.metadata_id == metadata_id,
        )
    ).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Instrument type metadata not found")
    db.delete(obj)
    db.commit()


@router.get("/strategy-types", response_model=list[TypeItem])
def list_strategy_types(db: Session = Depends(get_db)):
    result = db.execute(select(StrategyType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/strategy-types", status_code=201)
def create_strategy_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, StrategyType, data)


@router.get("/trade-statuses", response_model=list[TypeItem])
def list_trade_statuses(db: Session = Depends(get_db)):
    result = db.execute(select(TradeStatusType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/trade-statuses", status_code=201)
def create_trade_status_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, TradeStatusType, data)


@router.get("/order-types", response_model=list[TypeItem])
def list_order_types(db: Session = Depends(get_db)):
    result = db.execute(select(OrderType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/order-types", status_code=201)
def create_order_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, OrderType, data)


@router.get("/order-statuses", response_model=list[TypeItem])
def list_order_statuses(db: Session = Depends(get_db)):
    result = db.execute(select(OrderStatusType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/order-statuses", status_code=201)
def create_order_status_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, OrderStatusType, data)


@router.get("/transaction-types", response_model=list[TypeItem])
def list_transaction_types(db: Session = Depends(get_db)):
    result = db.execute(select(TransactionType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/transaction-types", status_code=201)
def create_transaction_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, TransactionType, data)


@router.get("/transaction-statuses", response_model=list[TypeItem])
def list_transaction_statuses(db: Session = Depends(get_db)):
    result = db.execute(select(TransactionStatusType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/transaction-statuses", status_code=201)
def create_transaction_status_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, TransactionStatusType, data)


# --- Exchange Types ---


@router.get("/exchange-types", response_model=list[TypeItem])
def list_exchange_types(db: Session = Depends(get_db)):
    result = db.execute(select(ExchangeType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/exchange-types", status_code=201)
def create_exchange_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, ExchangeType, data)


# --- Feed Types ---


@router.get("/feed-types", response_model=list[TypeItem])
def list_feed_types(db: Session = Depends(get_db)):
    result = db.execute(select(FeedType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/feed-types", status_code=201)
def create_feed_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, FeedType, data)


# ---- Composite Type endpoints ----


@router.get("/composite-types", response_model=list[CompositeTypeItem])
def list_composite_types(db: Session = Depends(get_db)):
    result = db.execute(select(CompositeType)).scalars().all()
    return [CompositeTypeItem.model_validate(r) for r in result]


@router.get("/composite-types/tree", response_model=list[CompositeTypeHierarchyItem])
def get_composite_type_tree(db: Session = Depends(get_db)):
    return build_type_tree(db, CompositeType)


@router.post("/composite-types", status_code=201, response_model=CompositeTypeItem)
def create_composite_type(data: CompositeTypeCreate, db: Session = Depends(get_db)):
    if data.parent_type_id:
        parent = db.get(CompositeType, data.parent_type_id)
        if not parent:
            raise NotFoundError("Parent composite type not found")
    obj = CompositeType(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        parent_type_id=data.parent_type_id,
        min_members=data.min_members,
        max_members=data.max_members,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return CompositeTypeItem.model_validate(obj)


@router.patch("/composite-types/{composite_type_id}", response_model=CompositeTypeItem)
def patch_composite_type(
    composite_type_id: str, data: CompositeTypePatch, db: Session = Depends(get_db)
):
    obj = db.get(CompositeType, composite_type_id)
    if not obj:
        raise NotFoundError("Composite type not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return CompositeTypeItem.model_validate(obj)


@router.get("/composite-types/{composite_type_id}/usage", response_model=EntityUsage)
def get_composite_type_usage(composite_type_id: str, db: Session = Depends(get_db)):
    return EntityUsage(items=[], total=0)


@router.delete("/composite-types/{composite_type_id}", status_code=204)
def delete_composite_type(composite_type_id: str, db: Session = Depends(get_db)):
    obj = db.get(CompositeType, composite_type_id)
    if not obj:
        raise NotFoundError("Composite type not found")
    db.delete(obj)
    db.commit()


# ---- Composite Type Metadata Requirements ----


@router.get(
    "/composite-types/{composite_type_id}/metadata",
    response_model=list[CompositeTypeMetadataSchema],
)
def list_composite_type_metadata(
    composite_type_id: str,
    include_inherited: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    # TODO: add get_effective_composite_type_metadata with inheritance support
    rows = (
        db.execute(
            select(CompositeTypeMetadata)
            .where(CompositeTypeMetadata.composite_type_id == composite_type_id)
            .order_by(CompositeTypeMetadata.display_order)
        )
        .scalars()
        .all()
    )
    return [
        CompositeTypeMetadataSchema(
            metadata_id=r.metadata_id,
            metadata_name=r.metadata_type.name,
            metadata_display_name=r.metadata_type.display_name,
            metadata_description=r.metadata_type.description,
            value_type=r.metadata_type.value_type,
            is_required=r.is_required,
            display_order=r.display_order,
        )
        for r in rows
    ]


@router.post(
    "/composite-types/{composite_type_id}/metadata",
    status_code=201,
    response_model=CompositeTypeMetadataSchema,
)
def add_composite_type_metadata(
    composite_type_id: str, data: CompositeTypeMetadataCreate, db: Session = Depends(get_db)
):
    existing = db.execute(
        select(CompositeTypeMetadata).where(
            CompositeTypeMetadata.composite_type_id == composite_type_id,
            CompositeTypeMetadata.metadata_id == data.metadata_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("Metadata field already linked to this composite type")

    new_meta = db.get(Metadata, data.metadata_id)
    if not new_meta:
        raise NotFoundError("Metadata type not found")

    obj = CompositeTypeMetadata(
        composite_type_id=composite_type_id,
        metadata_id=data.metadata_id,
        is_required=data.is_required,
        display_order=data.display_order,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return CompositeTypeMetadataSchema(
        metadata_id=obj.metadata_id,
        metadata_name=obj.metadata_type.name,
        metadata_display_name=obj.metadata_type.display_name,
        metadata_description=obj.metadata_type.description,
        value_type=obj.metadata_type.value_type,
        is_required=obj.is_required,
        display_order=obj.display_order,
    )


@router.delete("/composite-types/{composite_type_id}/metadata/{metadata_id}", status_code=204)
def remove_composite_type_metadata(
    composite_type_id: str, metadata_id: str, db: Session = Depends(get_db)
):
    obj = db.execute(
        select(CompositeTypeMetadata).where(
            CompositeTypeMetadata.composite_type_id == composite_type_id,
            CompositeTypeMetadata.metadata_id == metadata_id,
        )
    ).scalar_one_or_none()
    if not obj:
        raise NotFoundError("Composite type metadata not found")
    db.delete(obj)
    db.commit()
