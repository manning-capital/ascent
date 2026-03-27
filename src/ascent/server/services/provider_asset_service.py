import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models import (
    Asset,
    Metadata,
    Provider,
    ProviderAssetGroup,
    ProviderAssetGroupMember,
    ProviderAssetMetadata,
)
from ascent.server.exceptions import ConflictError, NotFoundError
from ascent.server.schemas.provider_assets import (
    AssetGroupCreate,
    AssetGroupMemberCreate,
    AssetGroupMemberSchema,
    AssetGroupSchema,
    AssetGroupUpdate,
    ProviderAssetLinkCreate,
    ProviderAssetLinkSchema,
)

# ---------------------------------------------------------------------------
# Provider-Asset Links (via ProviderAssetMetadata with "symbol" metadata)
# ---------------------------------------------------------------------------


def _get_or_create_symbol_metadata(db: Session) -> Metadata:
    md = db.scalar(select(Metadata).where(Metadata.name == "symbol"))
    if not md:
        md = Metadata(name="symbol", description="Provider-specific asset identifier/symbol")
        db.add(md)
        db.commit()
        db.refresh(md)
    return md


def get_provider_asset_links(
    db: Session,
    provider_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
) -> list[ProviderAssetLinkSchema]:
    symbol_md = db.scalar(select(Metadata).where(Metadata.name == "symbol"))
    if not symbol_md:
        return []

    query = (
        select(ProviderAssetMetadata)
        .options(
            joinedload(ProviderAssetMetadata.provider),
            joinedload(ProviderAssetMetadata.asset),
        )
        .where(ProviderAssetMetadata.metadata_id == symbol_md.id)
    )
    if provider_id:
        query = query.where(ProviderAssetMetadata.provider_id == provider_id)
    if asset_id:
        query = query.where(ProviderAssetMetadata.asset_id == asset_id)

    query = query.order_by(
        ProviderAssetMetadata.provider_id,
        ProviderAssetMetadata.asset_id,
        ProviderAssetMetadata.timestamp.desc(),
    )

    rows = db.execute(query).unique().scalars().all()

    # Deduplicate to latest per (provider_id, asset_id)
    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
    results: list[ProviderAssetLinkSchema] = []
    for r in rows:
        key = (r.provider_id, r.asset_id)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            ProviderAssetLinkSchema(
                provider_id=r.provider_id,
                provider_name=r.provider.name if r.provider else None,
                asset_id=r.asset_id,
                asset_name=r.asset.name if r.asset else None,
                asset_symbol=r.asset.symbol if r.asset else None,
                identifier=str(r.value) if r.value else "",
                created_at=r.created_at,
            )
        )
    return results


def create_provider_asset_link(
    db: Session, data: ProviderAssetLinkCreate
) -> ProviderAssetLinkSchema:
    symbol_md = _get_or_create_symbol_metadata(db)
    record = ProviderAssetMetadata(
        timestamp=datetime.datetime.now(datetime.UTC),
        provider_id=data.provider_id,
        asset_id=data.asset_id,
        metadata_id=symbol_md.id,
        value=data.identifier,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    provider = db.get(Provider, data.provider_id)
    asset = db.get(Asset, data.asset_id)
    return ProviderAssetLinkSchema(
        provider_id=data.provider_id,
        provider_name=provider.name if provider else None,
        asset_id=data.asset_id,
        asset_name=asset.name if asset else None,
        asset_symbol=asset.symbol if asset else None,
        identifier=data.identifier,
        created_at=record.created_at,
    )


def delete_provider_asset_link(db: Session, provider_id: uuid.UUID, asset_id: uuid.UUID) -> None:
    symbol_md = db.scalar(select(Metadata).where(Metadata.name == "symbol"))
    if not symbol_md:
        raise NotFoundError("Provider-asset link not found")
    rows = db.scalars(
        select(ProviderAssetMetadata).where(
            ProviderAssetMetadata.provider_id == provider_id,
            ProviderAssetMetadata.asset_id == asset_id,
            ProviderAssetMetadata.metadata_id == symbol_md.id,
        )
    ).all()
    if not rows:
        raise NotFoundError("Provider-asset link not found")
    for r in rows:
        db.delete(r)
    db.commit()


# ---------------------------------------------------------------------------
# Asset Groups
# ---------------------------------------------------------------------------


def get_asset_groups(db: Session) -> list[AssetGroupSchema]:
    query = (
        select(ProviderAssetGroup)
        .options(
            joinedload(ProviderAssetGroup.members).joinedload(ProviderAssetGroupMember.provider),
            joinedload(ProviderAssetGroup.members).joinedload(ProviderAssetGroupMember.from_asset),
            joinedload(ProviderAssetGroup.members).joinedload(ProviderAssetGroupMember.to_asset),
        )
        .order_by(ProviderAssetGroup.created_at.desc())
    )
    groups = db.execute(query).unique().scalars().all()
    return [_build_group_schema(g) for g in groups]


def get_asset_group(db: Session, group_id: uuid.UUID) -> AssetGroupSchema:
    query = (
        select(ProviderAssetGroup)
        .options(
            joinedload(ProviderAssetGroup.members).joinedload(ProviderAssetGroupMember.provider),
            joinedload(ProviderAssetGroup.members).joinedload(ProviderAssetGroupMember.from_asset),
            joinedload(ProviderAssetGroup.members).joinedload(ProviderAssetGroupMember.to_asset),
        )
        .where(ProviderAssetGroup.id == group_id)
    )
    g = db.execute(query).unique().scalar_one_or_none()
    if not g:
        raise NotFoundError("Asset group not found")
    return _build_group_schema(g)


def _validate_sequential_order(orders: list[int]) -> str | None:
    """Return an error message if orders are not unique and sequential from 1, else None."""
    if len(orders) != len(set(orders)):
        return "Member order values must be unique"
    if sorted(orders) != list(range(1, len(orders) + 1)):
        return "Member order values must be sequential starting from 1"
    return None


def create_asset_group(db: Session, data: AssetGroupCreate) -> ProviderAssetGroup:
    # Validate sequential order
    if data.members:
        err = _validate_sequential_order([m.order for m in data.members])
        if err:
            raise ConflictError(err)

    # Check for duplicate: a group with the exact same set of
    # (provider_id, from_asset_id, to_asset_id) members already exists.
    if data.members:
        new_member_set = frozenset(
            (m.provider_id, m.from_asset_id, m.to_asset_id) for m in data.members
        )
        new_count = len(new_member_set)

        # Find groups that have the same member count
        candidate_ids = (
            db.execute(
                select(ProviderAssetGroupMember.provider_asset_group_id)
                .group_by(ProviderAssetGroupMember.provider_asset_group_id)
                .having(func.count() == new_count)
            )
            .scalars()
            .all()
        )

        for gid in candidate_ids:
            existing_members = db.execute(
                select(
                    ProviderAssetGroupMember.provider_id,
                    ProviderAssetGroupMember.from_asset_id,
                    ProviderAssetGroupMember.to_asset_id,
                ).where(ProviderAssetGroupMember.provider_asset_group_id == gid)
            ).all()
            existing_set = frozenset(
                (row.provider_id, row.from_asset_id, row.to_asset_id) for row in existing_members
            )
            if existing_set == new_member_set:
                raise ConflictError(
                    "A group with the same set of provider asset pairs already exists"
                )

    group = ProviderAssetGroup(
        is_active=data.is_active,
    )
    for m in data.members:
        group.members.append(
            ProviderAssetGroupMember(
                provider_id=m.provider_id,
                from_asset_id=m.from_asset_id,
                to_asset_id=m.to_asset_id,
                order=m.order,
            )
        )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def update_asset_group(
    db: Session, group_id: uuid.UUID, data: AssetGroupUpdate
) -> ProviderAssetGroup:
    group = db.get(ProviderAssetGroup, group_id)
    if not group:
        raise NotFoundError("Asset group not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)
    return group


def delete_asset_group(db: Session, group_id: uuid.UUID) -> None:
    group = db.get(ProviderAssetGroup, group_id)
    if not group:
        raise NotFoundError("Asset group not found")
    db.delete(group)
    db.commit()


def add_group_member(
    db: Session, group_id: uuid.UUID, data: AssetGroupMemberCreate
) -> ProviderAssetGroupMember:
    # Order must be next in sequence
    current_count = (
        db.scalar(
            select(func.count()).where(ProviderAssetGroupMember.provider_asset_group_id == group_id)
        )
        or 0
    )
    if data.order != current_count + 1:
        raise ConflictError(f"Member order must be {current_count + 1} (next in sequence)")

    member = ProviderAssetGroupMember(
        provider_asset_group_id=group_id,
        provider_id=data.provider_id,
        from_asset_id=data.from_asset_id,
        to_asset_id=data.to_asset_id,
        order=data.order,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def remove_group_member(
    db: Session,
    group_id: uuid.UUID,
    provider_id: uuid.UUID,
    from_asset_id: uuid.UUID,
    to_asset_id: uuid.UUID,
) -> None:
    member = db.get(
        ProviderAssetGroupMember,
        (group_id, provider_id, from_asset_id, to_asset_id),
    )
    if not member:
        raise NotFoundError("Group member not found")
    db.delete(member)
    db.commit()


def _build_group_schema(g: ProviderAssetGroup) -> AssetGroupSchema:
    return AssetGroupSchema(
        id=g.id,
        is_active=g.is_active,
        members=[
            AssetGroupMemberSchema(
                provider_asset_group_id=m.provider_asset_group_id,
                provider_id=m.provider_id,
                provider_name=m.provider.name if m.provider else None,
                from_asset_id=m.from_asset_id,
                from_asset_symbol=m.from_asset.symbol or m.from_asset.name
                if m.from_asset
                else None,
                to_asset_id=m.to_asset_id,
                to_asset_symbol=m.to_asset.symbol or m.to_asset.name if m.to_asset else None,
                order=m.order,
            )
            for m in sorted(g.members, key=lambda x: x.order)
        ],
        created_at=g.created_at,
    )
