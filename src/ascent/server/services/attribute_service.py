from sqlalchemy import select
from sqlalchemy.orm import Session

from ascent.database.models import Attribute
from ascent.server.schemas.attributes import AttributeCreate


def get_attributes(db: Session) -> list[Attribute]:
    return list(db.execute(select(Attribute)).scalars().all())


def create_attribute(db: Session, data: AttributeCreate) -> Attribute:
    obj = Attribute(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
