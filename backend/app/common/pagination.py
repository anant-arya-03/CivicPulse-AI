from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, computed_field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=50)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):  # noqa: UP046  (PEP 695 syntax needs Python 3.12+)
    items: list[T]
    page: int
    page_size: int
    total: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.page_size))
