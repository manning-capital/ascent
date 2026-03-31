import uuid
from datetime import datetime

from sqlalchemy import MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy models.
    This class is used to define the base for all models in the application.
    It inherits from DeclarativeBase, which is a SQLAlchemy class that provides
    a declarative interface for defining models.
    """

    # Define the metadata for the models. This is used to define the primary key constraint name.
    metadata = MetaData(
        naming_convention={
            "pk": "%(table_name)s_pkey",
        }
    )


class NamedEntityMixin:
    """Mixin providing standardized fields for all named entities.

    Adds: id, name (unique identifier), display_name (human label),
    description, is_active, created_at, updated_at.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), server_onupdate=func.now()
    )
