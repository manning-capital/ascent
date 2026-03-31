import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ascent.database.models.composites import Composite, CompositeMember
from ascent.database.models.types import CompositeType
from ascent.server.exceptions import BadRequestError, ConflictError, NotFoundError
from ascent.server.schemas.composites import (
    CompositeCreate,
    CompositeMemberCreate,
    CompositeMemberSchema,
    CompositeSchema,
    CompositeUpdate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_sequential_order(orders: list[int]) -> str | None:
    """Return an error message if orders are not unique and sequential from 1, else None."""
    if len(orders) != len(set(orders)):
        return "Member order values must be unique"
    if sorted(orders) != list(range(1, len(orders) + 1)):
        return "Member order values must be sequential starting from 1"
    return None


def _validate_member_count(db: Session, composite_type_id: uuid.UUID, member_count: int) -> None:
    """Validate that the member count is within the composite type's allowed range."""
    composite_type = db.get(CompositeType, composite_type_id)
    if not composite_type:
        raise NotFoundError("Composite type not found")
    if member_count < composite_type.min_members:
        raise BadRequestError(
            f"Composite type '{composite_type.display_name}' requires at least "
            f"{composite_type.min_members} member(s), got {member_count}"
        )
    if member_count > composite_type.max_members:
        raise BadRequestError(
            f"Composite type '{composite_type.display_name}' allows at most "
            f"{composite_type.max_members} member(s), got {member_count}"
        )


def _build_composite_schema(c: Composite) -> CompositeSchema:
    return CompositeSchema(
        id=c.id,
        name=c.name,
        display_name=c.display_name,
        composite_type_id=c.composite_type_id,
        description=c.description,
        is_active=c.is_active,
        members=[
            CompositeMemberSchema(
                composite_id=m.composite_id,
                instrument_id=m.instrument_id,
                instrument_name=m.instrument.name if m.instrument else None,
                instrument_display_name=m.instrument.display_name if m.instrument else None,
                order=m.order,
            )
            for m in sorted(c.members, key=lambda x: x.order)
        ],
        created_at=c.created_at,
    )


# ---------------------------------------------------------------------------
# Composites
# ---------------------------------------------------------------------------


def get_composites(db: Session, min_members: int | None = None) -> list[CompositeSchema]:
    query = (
        select(Composite)
        .options(
            joinedload(Composite.members).joinedload(CompositeMember.instrument),
        )
        .order_by(Composite.created_at.desc())
    )
    if min_members is not None:
        query = query.where(
            Composite.id.in_(
                select(CompositeMember.composite_id)
                .group_by(CompositeMember.composite_id)
                .having(func.count() >= min_members)
            )
        )
    composites = db.execute(query).unique().scalars().all()
    return [_build_composite_schema(c) for c in composites]


def get_composite(db: Session, composite_id: uuid.UUID) -> CompositeSchema:
    query = (
        select(Composite)
        .options(
            joinedload(Composite.members).joinedload(CompositeMember.instrument),
        )
        .where(Composite.id == composite_id)
    )
    c = db.execute(query).unique().scalar_one_or_none()
    if not c:
        raise NotFoundError("Composite not found")
    return _build_composite_schema(c)


def create_composite(db: Session, data: CompositeCreate) -> CompositeSchema:
    # Validate member count against composite type
    _validate_member_count(db, data.composite_type_id, len(data.members))

    # Validate sequential order
    if data.members:
        err = _validate_sequential_order([m.order for m in data.members])
        if err:
            raise ConflictError(err)

    # Check for duplicate: a composite with the exact same set of instrument_ids
    if data.members:
        new_member_set = frozenset(m.instrument_id for m in data.members)
        new_count = len(new_member_set)

        # Find composites that have the same member count
        candidate_ids = (
            db.execute(
                select(CompositeMember.composite_id)
                .group_by(CompositeMember.composite_id)
                .having(func.count() == new_count)
            )
            .scalars()
            .all()
        )

        for cid in candidate_ids:
            existing_members = db.execute(
                select(CompositeMember.instrument_id).where(CompositeMember.composite_id == cid)
            ).all()
            existing_set = frozenset(row.instrument_id for row in existing_members)
            if existing_set == new_member_set:
                raise ConflictError("A composite with the same set of instruments already exists")

    composite = Composite(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        composite_type_id=data.composite_type_id,
        is_active=data.is_active,
    )
    for m in data.members:
        composite.members.append(
            CompositeMember(
                instrument_id=m.instrument_id,
                order=m.order,
            )
        )
    db.add(composite)
    db.commit()
    db.refresh(composite)

    return get_composite(db, composite.id)


def update_composite(
    db: Session, composite_id: uuid.UUID, data: CompositeUpdate
) -> CompositeSchema:
    composite = db.get(Composite, composite_id)
    if not composite:
        raise NotFoundError("Composite not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(composite, key, value)
    db.commit()
    db.refresh(composite)
    return get_composite(db, composite_id)


def delete_composite(db: Session, composite_id: uuid.UUID) -> None:
    composite = db.get(Composite, composite_id)
    if not composite:
        raise NotFoundError("Composite not found")
    db.delete(composite)
    db.commit()


def add_composite_member(
    db: Session, composite_id: uuid.UUID, data: CompositeMemberCreate
) -> CompositeSchema:
    composite = db.get(Composite, composite_id)
    if not composite:
        raise NotFoundError("Composite not found")

    # Order must be next in sequence
    current_count = (
        db.scalar(select(func.count()).where(CompositeMember.composite_id == composite_id)) or 0
    )
    if data.order != current_count + 1:
        raise ConflictError(f"Member order must be {current_count + 1} (next in sequence)")

    # Validate max member count
    _validate_member_count(db, composite.composite_type_id, current_count + 1)

    member = CompositeMember(
        composite_id=composite_id,
        instrument_id=data.instrument_id,
        order=data.order,
    )
    db.add(member)
    db.commit()

    return get_composite(db, composite_id)


def remove_composite_member(
    db: Session, composite_id: uuid.UUID, instrument_id: uuid.UUID
) -> CompositeSchema:
    member = db.get(CompositeMember, (composite_id, instrument_id))
    if not member:
        raise NotFoundError("Composite member not found")

    # Validate min member count
    composite = db.get(Composite, composite_id)
    current_count = (
        db.scalar(select(func.count()).where(CompositeMember.composite_id == composite_id)) or 0
    )
    composite_type = db.get(CompositeType, composite.composite_type_id)
    if composite_type and current_count - 1 < composite_type.min_members:
        raise BadRequestError(
            f"Cannot remove member: composite type '{composite_type.display_name}' "
            f"requires at least {composite_type.min_members} member(s)"
        )

    db.delete(member)
    db.commit()

    return get_composite(db, composite_id)
