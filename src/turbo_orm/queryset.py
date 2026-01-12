"""
AsyncQuerySet - Chainable async query builder for Django models.

Reuses Django's Query object for SQL generation, only replaces execution
with async cursors from django-async-backend.
"""

from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar

from django.db.models import Q
from django.db.models.sql import Query

if TYPE_CHECKING:
    from django.db.models import Model

T = TypeVar("T", bound="Model")


class AsyncQuerySet(Generic[T]):
    """
    Async query builder that wraps Django's Query object.

    Chainable methods (filter, exclude, order_by, etc.) return new AsyncQuerySet
    instances and don't hit the database.

    Terminal methods (aget, afirst, acount, etc.) are async and execute the query.
    """

    def __init__(
        self,
        model: type[T],
        query: Optional[Query] = None,
        using: str = "default",
    ):
        """
        Initialize AsyncQuerySet.

        Args:
            model: The Django model class this queryset is for
            query: Optional Django Query object (created if not provided)
            using: Database alias to use
        """
        self.model = model
        self.query = query if query is not None else Query(model)
        self._db = using
        self._prefetch_related_lookups: tuple = ()

    def _clone(self) -> "AsyncQuerySet[T]":
        """
        Create a copy of this queryset for chaining.

        Returns:
            A new AsyncQuerySet with cloned query
        """
        clone = self.__class__(
            model=self.model,
            query=self.query.chain(),
            using=self._db,
        )
        clone._prefetch_related_lookups = self._prefetch_related_lookups
        return clone

    # =========================================================================
    # Chainable methods - return new AsyncQuerySet, don't hit DB
    # =========================================================================

    def all(self) -> "AsyncQuerySet[T]":
        """Return a copy of this queryset."""
        return self._clone()

    def filter(self, *args: Any, **kwargs: Any) -> "AsyncQuerySet[T]":
        """
        Return a new queryset with the given filters applied.

        Args:
            *args: Q objects for complex filters
            **kwargs: Field lookups (field__lookup=value)

        Returns:
            New AsyncQuerySet with filters added
        """
        clone = self._clone()
        clone.query.add_q(Q(*args, **kwargs))
        return clone

    def exclude(self, *args: Any, **kwargs: Any) -> "AsyncQuerySet[T]":
        """
        Return a new queryset excluding objects matching the given filters.

        Args:
            *args: Q objects for complex filters
            **kwargs: Field lookups (field__lookup=value)

        Returns:
            New AsyncQuerySet with exclusion filters added
        """
        clone = self._clone()
        clone.query.add_q(~Q(*args, **kwargs))
        return clone

    def order_by(self, *fields: str) -> "AsyncQuerySet[T]":
        """
        Return a new queryset ordered by the given fields.

        Args:
            *fields: Field names to order by (prefix with '-' for descending)

        Returns:
            New AsyncQuerySet with ordering applied
        """
        clone = self._clone()
        clone.query.clear_ordering(force=True)
        clone.query.add_ordering(*fields)
        return clone

    def distinct(self, *fields: str) -> "AsyncQuerySet[T]":
        """
        Return a new queryset with DISTINCT applied.

        Args:
            *fields: Fields for DISTINCT ON (PostgreSQL only)

        Returns:
            New AsyncQuerySet with distinct applied
        """
        clone = self._clone()
        clone.query.add_distinct_fields(*fields)
        return clone

    def select_related(self, *fields: str) -> "AsyncQuerySet[T]":
        """
        Return a new queryset with SELECT ... JOIN for related fields.

        Args:
            *fields: Related field names to join

        Returns:
            New AsyncQuerySet with select_related applied
        """
        clone = self._clone()
        if fields:
            clone.query.add_select_related(fields)
        else:
            clone.query.select_related = True
        return clone

    def prefetch_related(self, *lookups: Any) -> "AsyncQuerySet[T]":
        """
        Return a new queryset with prefetch instructions.

        Note: Prefetching is executed after the main query.

        Args:
            *lookups: Prefetch objects or field names

        Returns:
            New AsyncQuerySet with prefetch lookups stored
        """
        clone = self._clone()
        clone._prefetch_related_lookups = clone._prefetch_related_lookups + lookups
        return clone

    def only(self, *fields: str) -> "AsyncQuerySet[T]":
        """
        Return a new queryset loading only the specified fields.

        Args:
            *fields: Field names to load

        Returns:
            New AsyncQuerySet with deferred loading configured
        """
        clone = self._clone()
        clone.query.add_immediate_loading(fields)
        return clone

    def defer(self, *fields: str) -> "AsyncQuerySet[T]":
        """
        Return a new queryset deferring the specified fields.

        Args:
            *fields: Field names to defer

        Returns:
            New AsyncQuerySet with deferred loading configured
        """
        clone = self._clone()
        clone.query.add_deferred_loading(fields)
        return clone

    def values(self, *fields: str, **expressions: Any) -> "AsyncQuerySet[T]":
        """
        Return a queryset that returns dictionaries instead of model instances.

        Args:
            *fields: Field names to include
            **expressions: Named expressions to include

        Returns:
            New AsyncQuerySet configured for dict output
        """
        clone = self._clone()
        clone.query.set_values(fields)
        if expressions:
            for alias, expr in expressions.items():
                clone.query.add_annotation(expr, alias)
        clone._iterable_class = "values"
        return clone

    def values_list(
        self, *fields: str, flat: bool = False, named: bool = False
    ) -> "AsyncQuerySet[T]":
        """
        Return a queryset that returns tuples instead of model instances.

        Args:
            *fields: Field names to include
            flat: If True and single field, return flat list
            named: If True, return named tuples

        Returns:
            New AsyncQuerySet configured for tuple output
        """
        clone = self._clone()
        clone.query.set_values(fields)
        clone._iterable_class = "values_list"
        clone._flat = flat
        clone._named = named
        return clone

    def annotate(self, *args: Any, **kwargs: Any) -> "AsyncQuerySet[T]":
        """
        Return a new queryset with annotations.

        Args:
            *args: Aggregate expressions with default names
            **kwargs: Named aggregate expressions

        Returns:
            New AsyncQuerySet with annotations added
        """
        clone = self._clone()
        for arg in args:
            # Positional args must be expressions with default_alias
            clone.query.add_annotation(arg, arg.default_alias)
        for alias, expr in kwargs.items():
            clone.query.add_annotation(expr, alias)
        return clone

    def using(self, alias: str) -> "AsyncQuerySet[T]":
        """
        Return a new queryset using the specified database.

        Args:
            alias: Database alias to use

        Returns:
            New AsyncQuerySet using the specified database
        """
        clone = self._clone()
        clone._db = alias
        return clone

    def __getitem__(self, k: Any) -> "AsyncQuerySet[T]":
        """
        Support slicing: qs[5:10] or qs[5]

        Args:
            k: Slice or index

        Returns:
            New AsyncQuerySet with limits applied
        """
        if isinstance(k, slice):
            clone = self._clone()
            start = k.start or 0
            stop = k.stop
            clone.query.set_limits(start, stop)
            return clone
        elif isinstance(k, int):
            if k < 0:
                raise ValueError("Negative indexing is not supported")
            clone = self._clone()
            clone.query.set_limits(k, k + 1)
            return clone
        else:
            raise TypeError(f"Invalid index type: {type(k)}")

    # =========================================================================
    # Terminal async methods - execute query and return results
    # These are implemented in phases 3-5
    # =========================================================================

    async def aget(self, *args: Any, **kwargs: Any) -> T:
        """
        Get a single object matching the given filters.

        Raises:
            DoesNotExist: If no object matches
            MultipleObjectsReturned: If more than one object matches

        Returns:
            The matching model instance
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        if args or kwargs:
            clone = self.filter(*args, **kwargs)
        else:
            clone = self._clone()

        # Limit to 2 to detect MultipleObjectsReturned
        clone.query.set_limits(0, 2)

        rows = await execute_query(clone.query, clone._db)

        if not rows:
            raise self.model.DoesNotExist(
                f"{self.model._meta.object_name} matching query does not exist."
            )
        if len(rows) > 1:
            raise self.model.MultipleObjectsReturned(
                f"get() returned more than one {self.model._meta.object_name} "
                f"-- it returned {len(rows)}!"
            )

        instances = rows_to_instances(self.model, rows, clone.query, clone._db)
        return instances[0]

    async def afirst(self) -> Optional[T]:
        """
        Return the first object, or None if no objects exist.

        Returns:
            The first model instance or None
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        clone = self._clone()

        # Add pk ordering if not already ordered
        if not clone.query.order_by:
            clone.query.add_ordering("pk")

        clone.query.set_limits(0, 1)

        rows = await execute_query(clone.query, clone._db)

        if not rows:
            return None

        instances = rows_to_instances(self.model, rows, clone.query, clone._db)
        return instances[0]

    async def alast(self) -> Optional[T]:
        """
        Return the last object, or None if no objects exist.

        Returns:
            The last model instance or None
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        clone = self._clone()

        # Add reversed pk ordering if not already ordered
        if not clone.query.order_by:
            clone.query.add_ordering("-pk")
        else:
            # Reverse existing ordering
            clone.query.standard_ordering = not clone.query.standard_ordering

        clone.query.set_limits(0, 1)

        rows = await execute_query(clone.query, clone._db)

        if not rows:
            return None

        instances = rows_to_instances(self.model, rows, clone.query, clone._db)
        return instances[0]

    async def acount(self) -> int:
        """
        Return the count of objects in the queryset.

        Returns:
            Integer count
        """
        from turbo_orm.execution import execute_count

        clone = self._clone()
        return await execute_count(clone.query, clone._db)

    async def aexists(self) -> bool:
        """
        Return True if any objects exist in the queryset.

        Returns:
            Boolean indicating existence
        """
        from turbo_orm.execution import execute_query

        clone = self._clone()
        clone.query.set_limits(0, 1)

        rows = await execute_query(clone.query, clone._db)
        return len(rows) > 0

    async def alist(self) -> list[T]:
        """
        Return all objects as a list.

        Returns:
            List of model instances
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        clone = self._clone()
        rows = await execute_query(clone.query, clone._db)
        return rows_to_instances(self.model, rows, clone.query, clone._db)

    async def __aiter__(self):
        """
        Async iteration over queryset results.

        Yields model instances one at a time using chunked fetching.
        """
        from turbo_orm.execution import execute_query_chunked
        from turbo_orm.utils import rows_to_instances

        clone = self._clone()

        async for chunk in execute_query_chunked(clone.query, clone._db, chunk_size=100):
            instances = rows_to_instances(self.model, chunk, clone.query, clone._db)
            for instance in instances:
                yield instance

    # =========================================================================
    # Write operations
    # =========================================================================

    async def acreate(self, **kwargs: Any) -> T:
        """
        Create and save a new object with the given kwargs.

        Args:
            **kwargs: Field values for the new object

        Returns:
            The created model instance
        """
        from turbo_orm.execution import execute_insert

        instance = self.model(**kwargs)
        await execute_insert(instance, self._db)
        return instance

    async def aupdate(self, **kwargs: Any) -> int:
        """
        Update all objects in the queryset with the given values.

        Args:
            **kwargs: Field values to update

        Returns:
            Number of rows updated
        """
        from turbo_orm.execution import execute_update

        clone = self._clone()
        return await execute_update(clone.query, kwargs, clone._db)

    async def adelete(self) -> tuple[int, dict[str, int]]:
        """
        Delete all objects in the queryset.

        Returns:
            Tuple of (total_deleted, {model_name: count})
        """
        from turbo_orm.execution import execute_delete

        clone = self._clone()
        return await execute_delete(clone.query, clone._db)

    async def abulk_create(
        self,
        objs: list[T],
        batch_size: Optional[int] = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Optional[list[str]] = None,
        unique_fields: Optional[list[str]] = None,
    ) -> list[T]:
        """
        Bulk create objects.

        Args:
            objs: List of model instances to create
            batch_size: Number of objects per batch
            ignore_conflicts: If True, ignore constraint violations
            update_conflicts: If True, update on conflict
            update_fields: Fields to update on conflict
            unique_fields: Fields that define uniqueness

        Returns:
            List of created instances
        """
        from turbo_orm.execution import execute_bulk_insert

        return await execute_bulk_insert(
            self.model,
            objs,
            self._db,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

    async def abulk_update(
        self,
        objs: list[T],
        fields: list[str],
        batch_size: Optional[int] = None,
    ) -> int:
        """
        Bulk update objects.

        Args:
            objs: List of model instances to update
            fields: Fields to update
            batch_size: Number of objects per batch

        Returns:
            Number of rows updated
        """
        from turbo_orm.execution import execute_bulk_update

        return await execute_bulk_update(
            self.model,
            objs,
            fields,
            self._db,
            batch_size=batch_size,
        )

    async def aget_or_create(
        self,
        defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[T, bool]:
        """
        Get an object or create it if it doesn't exist.

        Args:
            defaults: Values to use when creating
            **kwargs: Lookup parameters

        Returns:
            Tuple of (instance, created)
        """
        from django_async_backend.db.transaction import async_atomic

        defaults = defaults or {}

        async with async_atomic(using=self._db):
            try:
                instance = await self.aget(**kwargs)
                return instance, False
            except self.model.DoesNotExist:
                create_kwargs = {**kwargs, **defaults}
                instance = await self.acreate(**create_kwargs)
                return instance, True

    async def aupdate_or_create(
        self,
        defaults: Optional[dict[str, Any]] = None,
        create_defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[T, bool]:
        """
        Update an object or create it if it doesn't exist.

        Args:
            defaults: Values to update/create with
            create_defaults: Additional values only for creation
            **kwargs: Lookup parameters

        Returns:
            Tuple of (instance, created)
        """
        from django_async_backend.db.transaction import async_atomic

        defaults = defaults or {}
        create_defaults = create_defaults or {}

        async with async_atomic(using=self._db):
            try:
                instance = await self.aget(**kwargs)
                # Update existing
                for field, value in defaults.items():
                    setattr(instance, field, value)
                await execute_instance_update(instance, list(defaults.keys()), self._db)
                return instance, False
            except self.model.DoesNotExist:
                create_kwargs = {**kwargs, **defaults, **create_defaults}
                instance = await self.acreate(**create_kwargs)
                return instance, True

    async def ain_bulk(
        self,
        id_list: Optional[list[Any]] = None,
        *,
        field_name: str = "pk",
    ) -> dict[Any, T]:
        """
        Return a dictionary of objects keyed by their primary key or other field.

        Args:
            id_list: List of IDs to fetch (all if None)
            field_name: Field to use as dictionary key

        Returns:
            Dictionary mapping field values to instances
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        clone = self._clone()

        if id_list is not None:
            clone = clone.filter(**{f"{field_name}__in": id_list})

        rows = await execute_query(clone.query, clone._db)
        instances = rows_to_instances(self.model, rows, clone.query, clone._db)

        return {getattr(obj, field_name): obj for obj in instances}

    # =========================================================================
    # Aggregation
    # =========================================================================

    async def aaggregate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """
        Return a dictionary of aggregate values.

        Args:
            *args: Aggregate expressions
            **kwargs: Named aggregate expressions

        Returns:
            Dictionary of aggregate results
        """
        from turbo_orm.execution import execute_aggregate

        clone = self._clone()

        # Add aggregations
        for arg in args:
            clone.query.add_annotation(arg, arg.default_alias)
        for alias, expr in kwargs.items():
            clone.query.add_annotation(expr, alias)

        # Set default_cols to False for aggregate queries
        clone.query.default_cols = False
        clone.query.set_group_by(allow_aliases=False)

        return await execute_aggregate(clone.query, clone._db)

    # =========================================================================
    # Utility methods
    # =========================================================================

    def __repr__(self) -> str:
        return f"<AsyncQuerySet [{self.model.__name__}]>"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def db(self) -> str:
        """Return the database alias."""
        return self._db


# Helper for aupdate_or_create
async def execute_instance_update(instance, fields, using):
    """Update a single instance's fields."""
    from turbo_orm.execution import execute_instance_save

    await execute_instance_save(instance, fields, using)
