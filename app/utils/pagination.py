"""Pagination utilities for consistent API responses."""

from typing import Generic, TypeVar
from math import ceil

from pydantic import BaseModel

T = TypeVar("T")


class PageParams(BaseModel):
    """Page parameters for pagination."""

    page: int = 1
    page_size: int = 50

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database query."""
        return self.page_size


class PageResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
        cls, items: list[T], total: int, page: int, page_size: int
    ) -> "PageResponse[T]":
        """Create paginated response."""
        total_pages = ceil(total / page_size) if page_size > 0 else 0

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )
