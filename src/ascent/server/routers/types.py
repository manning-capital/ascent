from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import (
    AssetType,
    AssetTypeMetadata,
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
from ascent.server.dependencies import get_db
from ascent.server.exceptions import ConflictError, NotFoundError
from ascent.server.schemas.metadata import (
    AssetTypeMetadataCreate,
    AssetTypeMetadataSchema,
    MetadataTypeCreate,
    MetadataTypeSchema,
    ProviderTypeMetadataCreate,
    ProviderTypeMetadataSchema,
)
from ascent.server.schemas.types import TypeCreate, TypeItem, TypeItemWithSymbol

router = APIRouter(prefix="/types", tags=["types"])


def _create_type(db: Session, model_class, data: TypeCreate):
    obj = model_class(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/metadata-types", response_model=list[MetadataTypeSchema])
def list_metadata_types(db: Session = Depends(get_db)):
    result = db.execute(select(Metadata)).scalars().all()
    return [MetadataTypeSchema.model_validate(r) for r in result]


@router.post("/metadata-types", status_code=201, response_model=MetadataTypeSchema)
def create_metadata_type(data: MetadataTypeCreate, db: Session = Depends(get_db)):
    obj = Metadata(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return MetadataTypeSchema.model_validate(obj)


@router.get("/asset-types", response_model=list[TypeItem])
def list_asset_types(db: Session = Depends(get_db)):
    result = db.execute(select(AssetType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/asset-types", status_code=201)
def create_asset_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, AssetType, data)


# ---- Asset Type Metadata Requirements ----


@router.get("/asset-types/{asset_type_id}/metadata", response_model=list[AssetTypeMetadataSchema])
def list_asset_type_metadata(asset_type_id: str, db: Session = Depends(get_db)):
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


# ---- Other type endpoints ----


@router.get("/provider-types", response_model=list[TypeItem])
def list_provider_types(db: Session = Depends(get_db)):
    result = db.execute(select(ProviderType)).scalars().all()
    return [TypeItem.model_validate(r) for r in result]


@router.post("/provider-types", status_code=201)
def create_provider_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, ProviderType, data)


# ---- Provider Type Metadata Requirements ----


@router.get(
    "/provider-types/{provider_type_id}/metadata", response_model=list[ProviderTypeMetadataSchema]
)
def list_provider_type_metadata(provider_type_id: str, db: Session = Depends(get_db)):
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


@router.get("/strategy-types", response_model=list[TypeItemWithSymbol])
def list_strategy_types(db: Session = Depends(get_db)):
    result = db.execute(select(StrategyType)).scalars().all()
    return [TypeItemWithSymbol.model_validate(r) for r in result]


@router.post("/strategy-types", status_code=201)
def create_strategy_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, StrategyType, data)


@router.get("/trade-statuses", response_model=list[TypeItemWithSymbol])
def list_trade_statuses(db: Session = Depends(get_db)):
    result = db.execute(select(TradeStatusType)).scalars().all()
    return [TypeItemWithSymbol.model_validate(r) for r in result]


@router.post("/trade-statuses", status_code=201)
def create_trade_status_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, TradeStatusType, data)


@router.get("/order-types", response_model=list[TypeItemWithSymbol])
def list_order_types(db: Session = Depends(get_db)):
    result = db.execute(select(OrderType)).scalars().all()
    return [TypeItemWithSymbol.model_validate(r) for r in result]


@router.post("/order-types", status_code=201)
def create_order_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, OrderType, data)


@router.get("/order-statuses", response_model=list[TypeItemWithSymbol])
def list_order_statuses(db: Session = Depends(get_db)):
    result = db.execute(select(OrderStatusType)).scalars().all()
    return [TypeItemWithSymbol.model_validate(r) for r in result]


@router.post("/order-statuses", status_code=201)
def create_order_status_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, OrderStatusType, data)


@router.get("/transaction-types", response_model=list[TypeItemWithSymbol])
def list_transaction_types(db: Session = Depends(get_db)):
    result = db.execute(select(TransactionType)).scalars().all()
    return [TypeItemWithSymbol.model_validate(r) for r in result]


@router.post("/transaction-types", status_code=201)
def create_transaction_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, TransactionType, data)


@router.get("/transaction-statuses", response_model=list[TypeItemWithSymbol])
def list_transaction_statuses(db: Session = Depends(get_db)):
    result = db.execute(select(TransactionStatusType)).scalars().all()
    return [TypeItemWithSymbol.model_validate(r) for r in result]


@router.post("/transaction-statuses", status_code=201)
def create_transaction_status_type(data: TypeCreate, db: Session = Depends(get_db)):
    return _create_type(db, TransactionStatusType, data)
