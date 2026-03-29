import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models.asset_type_metadata import AssetTypeMetadata
from ascent.database.models.asset_type_provider_asset_metadata import AssetTypeProviderAssetMetadata
from ascent.database.models.provider_type_metadata import ProviderTypeMetadata
from ascent.database.models.types import AssetType, ProviderType
from ascent.server.exceptions import BadRequestError, NotFoundError
from ascent.server.schemas.metadata import (
    AssetTypeMetadataSchema,
    AssetTypeProviderAssetMetadataSchema,
    ProviderTypeMetadataSchema,
)
from ascent.server.schemas.types import TypeHierarchyItem


def get_type_ancestors(
    db: Session,
    model_class: type[AssetType] | type[ProviderType],
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
    model_class: type[AssetType] | type[ProviderType],
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
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.name,
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
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
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
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.name,
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
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
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
                is_required=r.is_required,
                display_order=r.display_order,
                is_inherited=True,
                source_type_id=ancestor.id,
                source_type_name=ancestor.name,
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
            metadata_description=r.metadata_type.description if r.metadata_type else None,
            value_type=r.metadata_type.value_type if r.metadata_type else "string",
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
    model_class: type[AssetType] | type[ProviderType],
) -> list[TypeHierarchyItem]:
    """Load all types and build a tree structure."""
    all_types = db.execute(select(model_class)).scalars().all()

    nodes: dict[uuid.UUID, TypeHierarchyItem] = {}
    for t in all_types:
        nodes[t.id] = TypeHierarchyItem(
            id=t.id,
            name=t.name,
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
