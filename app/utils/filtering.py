"""Filtering utilities for API queries."""

from typing import Any

from sqlalchemy import Select
from sqlalchemy.sql import ColumnElement


class FilterSet:
    """Base filter set for building query filters."""

    def __init__(self, query: Select):
        """Initialize filter set with a query."""
        self.query = query
        self._filters: list[ColumnElement[bool]] = []

    def add_filter(self, condition: ColumnElement[bool]) -> "FilterSet":
        """Add a filter condition."""
        if condition is not None:
            self._filters.append(condition)
        return self

    def apply(self) -> Select:
        """Apply all filters to the query."""
        for filter_condition in self._filters:
            self.query = self.query.where(filter_condition)
        return self.query


class SearchFilter:
    """Search filter for text fields."""

    @staticmethod
    def ilike(column: Any, value: str | None) -> ColumnElement[bool] | None:
        """Case-insensitive LIKE filter."""
        if value:
            return column.ilike(f"%{value}%")
        return None

    @staticmethod
    def equals(column: Any, value: Any) -> ColumnElement[bool] | None:
        """Equality filter."""
        if value is not None:
            return column == value
        return None

    @staticmethod
    def in_list(column: Any, values: list[Any] | None) -> ColumnElement[bool] | None:
        """IN filter for list of values."""
        if values:
            return column.in_(values)
        return None
