import re
from typing import Annotated, TypeVar

from pydantic import AfterValidator, BaseModel


def _validate_identifier(v: str) -> str:
    if not re.match(r"^[A-Z][A-Z0-9_]*$", v):
        raise ValueError(
            "Must start with an uppercase letter and contain only uppercase letters, numbers, and underscores"
        )
    return v


Identifier = Annotated[str, AfterValidator(_validate_identifier)]

T = TypeVar("T")


class NamedEntityCreate(BaseModel):
    name: Identifier
    display_name: str
    description: str | None = None


class NamedEntityUpdate(BaseModel):
    name: Identifier | None = None
    display_name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    columns: list[str] | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    status: int


class ErrorResponse(BaseModel):
    error: ErrorDetail
