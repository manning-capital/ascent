from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


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
