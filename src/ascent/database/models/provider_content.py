import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ascent.database.models.assets import Asset
from ascent.database.models.base import Base
from ascent.database.models.descriptors import Attribute, Metadata
from ascent.database.models.providers import Provider
from ascent.database.models.types import ContentType, SentimentType


class ProviderContent(Base):
    __tablename__ = "provider_content"
    __table_args__ = {
        "comment": "Stores provider content records. Text fields (authors, title, description, content) are stored in ProviderContentMetadata using the flexible metadata descriptor pattern."
    }

    id: Mapped[int] = mapped_column(
        primary_key=True, comment="The unique identifier of the provider content"
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        nullable=False, comment="The timestamp of the provider content"
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("provider.id"),
        nullable=False,
        comment="The identifier of the provider",
    )
    provider: Mapped["Provider"] = relationship("Provider")
    content_external_code: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="This is the external identifier for the content and will depend on the content provider and the type of content. For example, for a news article, it could be the URL of the article and for a social media post, it could be the post ID.",
    )
    content_type_id: Mapped[int] = mapped_column(
        ForeignKey("content_type.id"),
        nullable=False,
        comment="The identifier of the content type",
    )
    content_type: Mapped["ContentType"] = relationship("ContentType")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the provider content",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the provider content",
    )

    def __repr__(self):
        return f"{ProviderContent.__name__}(id={self.id}, provider_id={self.provider_id}, content_type_id={self.content_type_id}, content_external_code={self.content_external_code})"


class ProviderContentAttribute(Base):
    __tablename__ = "provider_content_attribute"
    __table_args__ = {
        "comment": "Stores attributes for provider content (e.g., sentiment scores). Uses a flexible attribute-based design where each attribute value is stored as a separate row, allowing new content attributes to be added without schema changes.",
        "postgresql_partition_by": "HASH (attribute_id)",
    }

    provider_content_id: Mapped[int] = mapped_column(
        ForeignKey("provider_content.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the provider content",
    )
    provider_content: Mapped["ProviderContent"] = relationship("ProviderContent")
    sentiment_type_id: Mapped[int] = mapped_column(
        ForeignKey("sentiment_type.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the sentiment type",
    )
    sentiment_type: Mapped["SentimentType"] = relationship("SentimentType")
    attribute_id: Mapped[int] = mapped_column(
        ForeignKey("attribute.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the attribute",
    )
    attribute: Mapped["Attribute"] = relationship("Attribute")
    attribute_value: Mapped[float] = mapped_column(
        nullable=False,
        comment="The value of the attribute for the provider content with the given sentiment type",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the provider content attribute",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the provider content attribute",
    )

    def __repr__(self):
        return f"{ProviderContentAttribute.__name__}(provider_content_id={self.provider_content_id}, sentiment_type_id={self.sentiment_type_id}, attribute_id={self.attribute_id}, attribute_value={self.attribute_value})"


class ProviderContentMetadata(Base):
    __tablename__ = "provider_content_metadata"
    __table_args__ = {
        "comment": "Stores text/metadata attributes for provider content (e.g., authors, title, description, content). Uses a flexible metadata-based design where each metadata value is stored as a separate row, allowing new content metadata to be added without schema changes. Similar to ProviderAssetMetadata but for content text fields.",
        "postgresql_partition_by": "HASH (metadata_id)",
    }

    timestamp: Mapped[datetime.datetime] = mapped_column(
        primary_key=True,
        nullable=False,
        comment="The timestamp when this metadata snapshot is valid. Part of the primary key to enable time-series metadata tracking and historical reconciliation.",
    )
    provider_content_id: Mapped[int] = mapped_column(
        ForeignKey("provider_content.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the provider content",
    )
    provider_content: Mapped["ProviderContent"] = relationship("ProviderContent")
    metadata_id: Mapped[int] = mapped_column(
        ForeignKey("metadata.id"),
        nullable=False,
        primary_key=True,
        comment="The identifier of the metadata type (e.g., 'authors', 'title', 'description', 'content'). References the Metadata table for metadata type definitions.",
    )
    metadata_type: Mapped["Metadata"] = relationship("Metadata")
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB,
        nullable=False,
        comment="The JSON value of the metadata attribute for this provider content. Can store text, numbers, booleans, objects, or arrays. For example, the actual title, description, or content text, or more complex structured data.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the metadata record",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_onupdate=func.now(),
        server_default=func.now(),
        comment="The timestamp of the last update of the metadata record",
    )

    def __repr__(self):
        return f"{ProviderContentMetadata.__name__}(timestamp={self.timestamp}, provider_content_id={self.provider_content_id}, metadata_id={self.metadata_id}, value={self.value})"


class AssetContent(Base):
    __tablename__ = "asset_content"
    __table_args__ = {
        "comment": "The asset content, will store the relationship between an asset and a provider content."
    }

    content_id: Mapped[int] = mapped_column(
        ForeignKey("provider_content.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the provider content",
    )
    provider_content: Mapped["ProviderContent"] = relationship("ProviderContent")
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("asset.id"),
        primary_key=True,
        nullable=False,
        comment="The identifier of the asset",
    )
    asset: Mapped["Asset"] = relationship("Asset")
    created_at: Mapped[datetime.datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        comment="The timestamp of the creation of the asset content",
    )
