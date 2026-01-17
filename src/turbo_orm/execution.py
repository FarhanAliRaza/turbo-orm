"""
SQL Execution Layer - Bridge between Django's SQL compiler and async cursors.

Uses Django's SQLCompiler to generate SQL and django-async-backend to execute
with true async cursors.

Connection handling:
- With pooling (OPTIONS["pool"]): borrows from pool, returns when done
- Without pooling: creates connection per query, closes when done
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Optional

from django.db import connections
from django.db.models.sql import Query

if TYPE_CHECKING:
    from django.db.models import Model


@asynccontextmanager
async def _get_cursor(using: str = "default"):
    """
    Get an async cursor using django-async-backend's connection handling.

    Closes connection after use to return it to the pool.
    """
    from django_async_backend.db import async_connections

    async_conn = async_connections[using]
    try:
        async with async_conn._cursor() as cursor:
            yield cursor
    finally:
        await async_conn.close()


async def execute_query(query: Query, using: str = "default") -> list[tuple]:
    """
    Execute a SELECT query and return all rows.

    Args:
        query: Django Query object
        using: Database alias

    Returns:
        List of tuples (rows)
    """
    # Get SQL from Django's compiler
    connection = connections[using]
    compiler = query.get_compiler(using=using, connection=connection)
    sql, params = compiler.as_sql()

    # Execute with async cursor
    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)
        rows = await cursor.fetchall()
        return list(rows)


async def execute_query_chunked(
    query: Query,
    using: str = "default",
    chunk_size: int = 100,
) -> AsyncIterator[list[tuple]]:
    """
    Execute a SELECT query and yield rows in chunks.

    Args:
        query: Django Query object
        using: Database alias
        chunk_size: Number of rows per chunk

    Yields:
        Lists of tuples (row chunks)
    """
    connection = connections[using]
    compiler = query.get_compiler(using=using, connection=connection)
    sql, params = compiler.as_sql()

    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)

        while True:
            rows = await cursor.fetchmany(chunk_size)
            if not rows:
                break
            yield list(rows)


async def execute_count(query: Query, using: str = "default") -> int:
    """
    Execute a COUNT query and return the count.

    Args:
        query: Django Query object
        using: Database alias

    Returns:
        Integer count
    """
    connection = connections[using]
    model = query.model
    opts = model._meta

    # Build a simple COUNT(*) query
    table = connection.ops.quote_name(opts.db_table)

    # Get WHERE clause from original query
    compiler = query.get_compiler(using=using, connection=connection)

    # Build WHERE clause if any filters exist
    where_sql = ""
    params = []
    if query.where:
        where_clause, where_params = compiler.compile(query.where)
        if where_clause:
            where_sql = f" WHERE {where_clause}"
            params = list(where_params)

    sql = f"SELECT COUNT(*) FROM {table}{where_sql}"

    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def execute_aggregate(query: Query, using: str = "default") -> dict[str, Any]:
    """
    Execute an aggregate query and return the results.

    Args:
        query: Django Query object with annotations
        using: Database alias

    Returns:
        Dictionary of aggregate results
    """
    connection = connections[using]

    # Clear ordering for aggregates
    query.clear_ordering(force=True)

    compiler = query.get_compiler(using=using, connection=connection)
    sql, params = compiler.as_sql()

    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)
        row = await cursor.fetchone()

        if row:
            # Map column names to values
            result = {}
            for i, annotation in enumerate(query.annotation_select.keys()):
                result[annotation] = row[i]
            return result
        return {}


async def execute_insert(instance: "Model", using: str = "default") -> None:
    """
    Insert a model instance into the database.

    Uses RETURNING to get the auto-generated primary key.

    Args:
        instance: Model instance to insert
        using: Database alias
    """
    model = instance.__class__
    opts = model._meta
    connection = connections[using]

    # Get fields to insert
    fields = [f for f in opts.concrete_fields if not f.primary_key or not f.auto_created]

    # Build column names and values
    columns = []
    values = []
    params = []

    for field in fields:
        value = field.pre_save(instance, add=True)
        if value is not None or not field.null:
            columns.append(connection.ops.quote_name(field.column))
            values.append("%s")
            params.append(field.get_db_prep_save(value, connection=connection))

    # Build SQL
    table = connection.ops.quote_name(opts.db_table)
    pk_column = connection.ops.quote_name(opts.pk.column)

    if columns:
        cols = ", ".join(columns)
        vals = ", ".join(values)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({vals}) RETURNING {pk_column}"
    else:
        # Model with no fields (just auto pk)
        sql = f"INSERT INTO {table} DEFAULT VALUES RETURNING {pk_column}"
        params = []

    # Execute
    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)
        row = await cursor.fetchone()

        if row:
            # Set the primary key
            setattr(instance, opts.pk.attname, row[0])

    # Update instance state
    instance._state.adding = False
    instance._state.db = using


async def execute_instance_save(
    instance: "Model",
    update_fields: list[str],
    using: str = "default",
) -> None:
    """
    Update specific fields of an existing model instance.

    Args:
        instance: Model instance to update
        update_fields: List of field names to update
        using: Database alias
    """
    model = instance.__class__
    opts = model._meta
    connection = connections[using]
    pk_value = instance.pk

    # Get fields to update
    fields = [opts.get_field(name) for name in update_fields]

    # Build SET clause
    set_clauses = []
    params = []

    for field in fields:
        value = getattr(instance, field.attname)
        col = connection.ops.quote_name(field.column)
        set_clauses.append(f"{col} = %s")
        params.append(field.get_db_prep_save(value, connection=connection))

    # Build SQL
    table = connection.ops.quote_name(opts.db_table)
    pk_column = connection.ops.quote_name(opts.pk.column)
    params.append(pk_value)

    sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {pk_column} = %s"

    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)


async def execute_update(
    query: Query,
    values: dict[str, Any],
    using: str = "default",
) -> int:
    """
    Execute an UPDATE query.

    Args:
        query: Django Query object (for WHERE clause)
        values: Dictionary of field -> value to update
        using: Database alias

    Returns:
        Number of rows updated
    """
    from django.db.models.sql import UpdateQuery

    connection = connections[using]
    model = query.model
    opts = model._meta

    # Create an UpdateQuery
    update_query = UpdateQuery(model)
    update_query.where = query.where.clone()

    # Add values to update
    for field_name, value in values.items():
        field = opts.get_field(field_name)
        update_query.add_update_values({field.name: value})

    # Compile and execute
    compiler = update_query.get_compiler(using=using, connection=connection)
    sql, params = compiler.as_sql()

    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)
        return cursor.rowcount


async def execute_delete(
    query: Query,
    using: str = "default",
) -> tuple[int, dict[str, int]]:
    """
    Execute a DELETE query.

    Args:
        query: Django Query object (for WHERE clause)
        using: Database alias

    Returns:
        Tuple of (total_deleted, {model_label: count})
    """
    from django.db.models.sql import DeleteQuery

    connection = connections[using]
    model = query.model
    opts = model._meta

    # Create a DeleteQuery
    delete_query = DeleteQuery(model)
    delete_query.where = query.where.clone()

    # Compile and execute
    compiler = delete_query.get_compiler(using=using, connection=connection)
    sql, params = compiler.as_sql()

    async with _get_cursor(using) as cursor:
        await cursor.execute(sql, params)
        count = cursor.rowcount

    return count, {opts.label: count}


async def execute_bulk_insert(
    model: type["Model"],
    objs: list["Model"],
    using: str = "default",
    batch_size: Optional[int] = None,
    ignore_conflicts: bool = False,
    update_conflicts: bool = False,
    update_fields: Optional[list[str]] = None,
    unique_fields: Optional[list[str]] = None,
) -> list["Model"]:
    """
    Bulk insert model instances.

    Args:
        model: Model class
        objs: List of instances to insert
        using: Database alias
        batch_size: Batch size for inserts
        ignore_conflicts: Ignore conflicts
        update_conflicts: Update on conflict
        update_fields: Fields to update on conflict
        unique_fields: Fields for conflict detection

    Returns:
        List of inserted instances (with PKs set)
    """
    if not objs:
        return []

    opts = model._meta
    connection = connections[using]

    # Get fields to insert
    fields = [f for f in opts.concrete_fields if not f.primary_key or not f.auto_created]

    columns = [connection.ops.quote_name(f.column) for f in fields]
    table = connection.ops.quote_name(opts.db_table)
    pk_column = connection.ops.quote_name(opts.pk.column)

    # Default batch size
    if batch_size is None:
        batch_size = len(objs)

    results = []

    # Process in batches
    for i in range(0, len(objs), batch_size):
        batch = objs[i : i + batch_size]

        # Build values
        all_params = []
        value_rows = []

        for obj in batch:
            row_params = []
            for field in fields:
                value = field.pre_save(obj, add=True)
                row_params.append(field.get_db_prep_save(value, connection=connection))
            all_params.extend(row_params)
            placeholders = ", ".join(["%s"] * len(fields))
            value_rows.append(f"({placeholders})")

        # Build SQL
        values_sql = ", ".join(value_rows)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES {values_sql}"

        # Handle conflicts
        if ignore_conflicts:
            sql += " ON CONFLICT DO NOTHING"
        elif update_conflicts and update_fields and unique_fields:
            unique_cols = [
                connection.ops.quote_name(opts.get_field(f).column) for f in unique_fields
            ]
            update_cols = []
            for f in update_fields:
                col = connection.ops.quote_name(opts.get_field(f).column)
                update_cols.append(f"{col} = EXCLUDED.{col}")
            sql += f" ON CONFLICT ({', '.join(unique_cols)}) DO UPDATE SET {', '.join(update_cols)}"

        sql += f" RETURNING {pk_column}"

        # Execute
        async with _get_cursor(using) as cursor:
            await cursor.execute(sql, all_params)
            rows = await cursor.fetchall()

            # Set PKs on objects
            for obj, row in zip(batch, rows):
                setattr(obj, opts.pk.attname, row[0])
                obj._state.adding = False
                obj._state.db = using

            results.extend(batch)

    return results


async def execute_bulk_update(
    model: type["Model"],
    objs: list["Model"],
    fields: list[str],
    using: str = "default",
    batch_size: Optional[int] = None,
) -> int:
    """
    Bulk update model instances.

    Args:
        model: Model class
        objs: List of instances to update
        fields: Fields to update
        using: Database alias
        batch_size: Batch size for updates

    Returns:
        Number of rows updated
    """
    if not objs or not fields:
        return 0

    opts = model._meta
    connection = connections[using]

    # Default batch size
    if batch_size is None:
        batch_size = len(objs)

    total_updated = 0

    # Get field objects
    field_objs = [opts.get_field(name) for name in fields]
    pk_column = connection.ops.quote_name(opts.pk.column)
    table = connection.ops.quote_name(opts.db_table)

    # Process in batches
    for i in range(0, len(objs), batch_size):
        batch = objs[i : i + batch_size]

        # Update each object individually (simple approach)
        # A more optimized approach would use CASE WHEN
        for obj in batch:
            set_clauses = []
            params = []

            for field in field_objs:
                value = getattr(obj, field.attname)
                col = connection.ops.quote_name(field.column)
                set_clauses.append(f"{col} = %s")
                params.append(field.get_db_prep_save(value, connection=connection))

            params.append(obj.pk)

            sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {pk_column} = %s"

            async with _get_cursor(using) as cursor:
                await cursor.execute(sql, params)
                total_updated += cursor.rowcount

    return total_updated
