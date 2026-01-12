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

    Handles select_related data by hydrating related objects from JOINed columns.

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

    # Check if we have select_related
    has_select_related = query.select_related and query.select_related is not True

    if has_select_related:
        return _rows_to_instances_with_related(model, rows, query, using)

    # Simple case: no select_related
    opts = model._meta
    fields = opts.concrete_fields
    field_names = [f.attname for f in fields]

    instances = []

    for row in rows:
        instance = model.from_db(
            using,
            field_names[: len(row)],
            list(row[: len(field_names)]),
        )
        instances.append(instance)

    return instances


def _rows_to_instances_with_related(
    model: type["Model"],
    rows: list[tuple],
    query: Query,
    using: str = "default",
) -> list["Model"]:
    """
    Convert database rows to model instances with select_related data.

    Parses column mapping from Django's compiler to hydrate related objects.
    """
    connection = connections[using]
    compiler = query.get_compiler(using=using, connection=connection)

    # Force the compiler to set up select and klass_info
    # This is normally done during as_sql() but we need it for row mapping
    if not hasattr(compiler, "klass_info") or compiler.klass_info is None:
        compiler.pre_sql_setup()
        if hasattr(compiler, "setup_query"):
            compiler.setup_query()

    klass_info = getattr(compiler, "klass_info", None)

    # If still no klass_info, fall back to simple instance creation
    if klass_info is None:
        opts = model._meta
        fields = opts.concrete_fields
        field_names = [f.attname for f in fields]

        instances = []
        for row in rows:
            instance = model.from_db(
                using,
                field_names[: len(row)],
                list(row[: len(field_names)]),
            )
            instances.append(instance)
        return instances

    instances = []

    for row in rows:
        instance = _create_instance_from_row(model, row, klass_info, compiler, using)
        instances.append(instance)

    return instances


def _create_instance_from_row(
    model: type["Model"],
    row: tuple,
    klass_info: dict,
    compiler: Any,
    using: str,
) -> "Model":
    """
    Create a model instance from a row, including related objects.

    Uses Django's klass_info structure which contains column indices.
    """
    # klass_info structure:
    # {
    #   'model': Model,
    #   'select_fields': [0, 1, 2, ...],  # indices into compiler.select
    #   'related_klass_infos': [
    #     {'model': RelatedModel, 'select_fields': [...], 'field': field_instance, ...},
    #     ...
    #   ]
    # }

    # Extract field values for main model
    select_indices = klass_info.get("select_fields", [])
    field_names = []
    field_values = []

    for idx in select_indices:
        col = compiler.select[idx][0]  # First element of tuple is the Col
        field = col.target
        field_names.append(field.attname)
        field_values.append(row[idx])

    # Create main instance
    instance = model.from_db(using, field_names, field_values)

    # Process related objects
    related_infos = klass_info.get("related_klass_infos", [])
    for related_info in related_infos:
        _hydrate_related(instance, row, related_info, compiler, using)

    return instance


def _hydrate_related(
    instance: "Model",
    row: tuple,
    related_info: dict,
    compiler: Any,
    using: str,
) -> None:
    """
    Hydrate a related object from row data and attach to instance.
    """
    related_model = related_info["model"]
    select_indices = related_info.get("select_fields", [])
    field = related_info.get("field")

    if not select_indices or not field:
        return

    # Get the field name to use for setting the related object
    field_name = field.name

    # Extract related field values
    field_names = []
    field_values = []

    for idx in select_indices:
        col = compiler.select[idx][0]
        rel_field = col.target
        field_names.append(rel_field.attname)
        field_values.append(row[idx])

    # Check if all values are None (LEFT JOIN with no match)
    if all(v is None for v in field_values):
        setattr(instance, field_name, None)
        return

    # Create related instance
    related_instance = related_model.from_db(using, field_names, field_values)

    # Set on parent instance
    setattr(instance, field_name, related_instance)

    # Cache in _state.fields_cache for Django's cached property access
    if not hasattr(instance._state, "fields_cache"):
        instance._state.fields_cache = {}
    instance._state.fields_cache[field_name] = related_instance

    # Process nested related objects recursively
    nested_infos = related_info.get("related_klass_infos", [])
    for nested_info in nested_infos:
        _hydrate_related(related_instance, row, nested_info, compiler, using)


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
