"""Schemas for the Data Explorer endpoints."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class FilterOption(BaseModel):
    id: uuid.UUID
    display_name: str


class DataExplorerFilterOptions(BaseModel):
    entities: list[FilterOption]
    descriptors: list[FilterOption]
    periods: list[FilterOption] | None = None


class DataSourceInfo(BaseModel):
    table: str
    label: str
    entity_type: str
    descriptor_type: str
    has_period: bool
