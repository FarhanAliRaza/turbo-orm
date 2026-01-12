"""
Utility functions for turbo-orm.

Handles conversion of database rows to model instances.
"""

from typing import TYPE_CHECKING, Any

from django.db import connections
from django.db.models.sql import Query

if TYPE_CHECKING:
    from django.db.models import Model


def rows_to_instances(
    model: type["Model"],
    rows: list[tuple],
    query: Query,
    using: str = "default",
) -> list["Model"]:
    """
    Convert database rows to model instances.

    Args:
        model: The model class
        rows: List of tuples from database
        query: The Query object used (for field info)
        using: Database alias

    Returns:
        List of model instances
    """
    if not rows:
        return []

    opts = model._meta
    fields = opts.concrete_fields
    field_names = [f.attname for f in fields]

    instances = []

    for row in rows:
        # Create instance via from_db
        instance = model.from_db(
            using,
            field_names[:len(row)],
            list(row[:len(field_names)]),
        )
        instances.append(instance)

    return instances


def get_concrete_fields(model: type["Model"]) -> list:
    """
    Get the concrete (database-backed) fields for a model.

    Args:
        model: The model class

    Returns:
        List of concrete field objects
    """
    return list(model._meta.concrete_fields)


def get_field_names(model: type["Model"]) -> list[str]:
    """
    Get the attribute names of concrete fields.

    Args:
        model: The model class

    Returns:
        List of field attribute names
    """
    return [f.attname for f in model._meta.concrete_fields]


def get_field_columns(model: type["Model"]) -> list[str]:
    """
    Get the database column names for concrete fields.

    Args:
        model: The model class

    Returns:
        List of column names
    """
    return [f.column for f in model._meta.concrete_fields]


def model_to_dict(
    instance: "Model",
    fields: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    """
    Convert a model instance to a dictionary.

    Args:
        instance: The model instance
        fields: Fields to include (all if None)
        exclude: Fields to exclude

    Returns:
        Dictionary of field values
    """
    opts = instance._meta
    data = {}

    for f in opts.concrete_fields:
        if fields is not None and f.attname not in fields:
            continue
        if exclude is not None and f.attname in exclude:
            continue
        data[f.attname] = getattr(instance, f.attname)

    return data
