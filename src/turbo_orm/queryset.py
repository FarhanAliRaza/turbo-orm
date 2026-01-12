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
        self._result_cache: Optional[list[T]] = None

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
        # Don't copy _result_cache - new clone should fetch fresh data
        return clone

    def __iter__(self):
        """
        Synchronous iteration over cached results.

        Only works after the queryset has been evaluated (e.g., via async for).
        Raises RuntimeError if the cache is empty.
        """
        if self._result_cache is None:
            raise RuntimeError(
                "Cannot iterate synchronously over AsyncQuerySet before it has been "
                "evaluated. Use 'async for' or 'await qs.alist()' first."
            )
        return iter(self._result_cache)

    def __len__(self) -> int:
        """
        Return the length of cached results.

        Only works after the queryset has been evaluated.
        """
        if self._result_cache is None:
            raise RuntimeError(
                "Cannot get length of AsyncQuerySet before it has been evaluated. "
                "Use 'await qs.acount()' or evaluate with 'await qs.alist()' first."
            )
        return len(self._result_cache)

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
        # Return cached results if available
        if self._result_cache is not None:
            return list(self._result_cache)

        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        rows = await execute_query(self.query, self._db)
        instances = rows_to_instances(self.model, rows, self.query, self._db)

        # Execute prefetch_related
        if self._prefetch_related_lookups:
            await self._do_prefetch(instances)

        # Cache results
        self._result_cache = instances

        return instances

    async def __aiter__(self):
        """
        Async iteration over queryset results.

        Fetches all results first to avoid holding connection during iteration.
        This allows nested queries inside the loop without pool exhaustion.
        Also populates _result_cache for subsequent sync iteration.
        """
        # If already cached, yield from cache
        if self._result_cache is not None:
            for instance in self._result_cache:
                yield instance
            return

        # Fetch all results first (releases connection before iteration)
        # This prevents connection starvation when nesting queries in the loop
        instances = await self.alist()

        for instance in instances:
            yield instance

    # =========================================================================
    # Prefetch related helpers
    # =========================================================================

    async def _do_prefetch(self, instances: list[T]) -> None:
        """
        Execute prefetch_related lookups for the given instances.

        Args:
            instances: List of model instances to prefetch for
        """
        if not self._prefetch_related_lookups or not instances:
            return

        for lookup in self._prefetch_related_lookups:
            await self._prefetch_one_level(instances, lookup)

    async def _prefetch_one_level(self, instances: list[T], lookup: Any) -> None:
        """
        Execute a single prefetch lookup.

        Args:
            instances: Parent instances to prefetch for
            lookup: Lookup string or Prefetch object
        """
        from django.db.models import Prefetch

        # Handle Prefetch object vs string lookup
        if isinstance(lookup, Prefetch):
            attr_name = lookup.prefetch_to.split("__")[0]
            custom_queryset = lookup.queryset
        elif isinstance(lookup, str):
            attr_name = lookup.split("__")[0]
            custom_queryset = None
        else:
            return

        # Get the field descriptor
        try:
            field = self.model._meta.get_field(attr_name)
        except Exception:
            return

        # Determine relationship type and fetch accordingly
        if field.many_to_many:
            await self._prefetch_many_to_many(instances, field, attr_name, custom_queryset)
        elif field.one_to_many:
            await self._prefetch_reverse_fk(instances, field, attr_name, custom_queryset)
        elif field.is_relation and not field.many_to_one:
            await self._prefetch_reverse_one_to_one(instances, field, attr_name, custom_queryset)
        else:
            # Forward FK or OneToOne
            await self._prefetch_forward_relation(instances, field, attr_name, custom_queryset)

    async def _prefetch_forward_relation(
        self,
        instances: list[T],
        field: Any,
        attr_name: str,
        custom_queryset: Any,
    ) -> None:
        """
        Prefetch forward ForeignKey or OneToOne relations.
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        related_model = field.related_model

        # Get all related PKs
        related_pks = [
            getattr(obj, field.attname)
            for obj in instances
            if getattr(obj, field.attname) is not None
        ]

        if not related_pks:
            return

        # Build query for related objects
        if custom_queryset is not None:
            qs = custom_queryset.filter(pk__in=related_pks)
        else:
            qs = AsyncQuerySet(related_model, using=self._db).filter(pk__in=related_pks)

        rows = await execute_query(qs.query, qs._db)
        related_objects = rows_to_instances(related_model, rows, qs.query, qs._db)

        # Build lookup dict
        related_dict = {obj.pk: obj for obj in related_objects}

        # Assign to instances
        for instance in instances:
            related_pk = getattr(instance, field.attname)
            if related_pk:
                related_obj = related_dict.get(related_pk)
                setattr(instance, attr_name, related_obj)
                if not hasattr(instance._state, "fields_cache"):
                    instance._state.fields_cache = {}
                instance._state.fields_cache[attr_name] = related_obj

    async def _prefetch_reverse_fk(
        self,
        instances: list[T],
        field: Any,
        attr_name: str,
        custom_queryset: Any,
    ) -> None:
        """
        Prefetch reverse ForeignKey relations (one-to-many).
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        related_model = field.related_model
        related_field_name = field.field.name  # The FK field on the related model

        # Get all parent PKs
        instance_pks = [obj.pk for obj in instances]

        # Build query for related objects
        if custom_queryset is not None:
            qs = custom_queryset.filter(**{f"{related_field_name}__in": instance_pks})
        else:
            qs = AsyncQuerySet(related_model, using=self._db).filter(
                **{f"{related_field_name}__in": instance_pks}
            )

        rows = await execute_query(qs.query, qs._db)
        related_objects = rows_to_instances(related_model, rows, qs.query, qs._db)

        # Group by parent instance
        cache = {}
        for related in related_objects:
            parent_pk = getattr(related, f"{related_field_name}_id")
            cache.setdefault(parent_pk, []).append(related)

        # Assign to instances
        for instance in instances:
            if not hasattr(instance, "_prefetched_objects_cache"):
                instance._prefetched_objects_cache = {}
            instance._prefetched_objects_cache[attr_name] = cache.get(instance.pk, [])

    async def _prefetch_many_to_many(
        self,
        instances: list[T],
        field: Any,
        attr_name: str,
        custom_queryset: Any,
    ) -> None:
        """
        Prefetch ManyToMany relations.
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        related_model = field.related_model

        # Get all parent PKs
        instance_pks = [obj.pk for obj in instances]

        # Get the M2M through table info
        m2m = field.remote_field.through
        source_field_name = field.m2m_column_name()
        target_field_name = field.m2m_reverse_name()

        # Query the through table to get mappings
        through_query = f"""
            SELECT {source_field_name}, {target_field_name}
            FROM {m2m._meta.db_table}
            WHERE {source_field_name} = ANY(%s)
        """

        from turbo_orm.execution import _get_cursor

        async with _get_cursor(self._db) as cursor:
            await cursor.execute(through_query, [instance_pks])
            through_rows = await cursor.fetchall()

        # Build mapping from parent pk to related pks
        related_pk_map = {}
        all_related_pks = set()
        for source_pk, target_pk in through_rows:
            related_pk_map.setdefault(source_pk, []).append(target_pk)
            all_related_pks.add(target_pk)

        if not all_related_pks:
            # No related objects, set empty lists
            for instance in instances:
                if not hasattr(instance, "_prefetched_objects_cache"):
                    instance._prefetched_objects_cache = {}
                instance._prefetched_objects_cache[attr_name] = []
            return

        # Fetch all related objects
        if custom_queryset is not None:
            qs = custom_queryset.filter(pk__in=list(all_related_pks))
        else:
            qs = AsyncQuerySet(related_model, using=self._db).filter(pk__in=list(all_related_pks))

        rows = await execute_query(qs.query, qs._db)
        related_objects = rows_to_instances(related_model, rows, qs.query, qs._db)

        # Build lookup dict
        related_dict = {obj.pk: obj for obj in related_objects}

        # Assign to instances
        for instance in instances:
            if not hasattr(instance, "_prefetched_objects_cache"):
                instance._prefetched_objects_cache = {}
            related_pks = related_pk_map.get(instance.pk, [])
            instance._prefetched_objects_cache[attr_name] = [
                related_dict[pk] for pk in related_pks if pk in related_dict
            ]

    async def _prefetch_reverse_one_to_one(
        self,
        instances: list[T],
        field: Any,
        attr_name: str,
        custom_queryset: Any,
    ) -> None:
        """
        Prefetch reverse OneToOne relations.
        """
        from turbo_orm.execution import execute_query
        from turbo_orm.utils import rows_to_instances

        related_model = field.related_model
        related_field_name = field.field.name

        # Get all parent PKs
        instance_pks = [obj.pk for obj in instances]

        # Build query
        if custom_queryset is not None:
            qs = custom_queryset.filter(**{f"{related_field_name}__in": instance_pks})
        else:
            qs = AsyncQuerySet(related_model, using=self._db).filter(
                **{f"{related_field_name}__in": instance_pks}
            )

        rows = await execute_query(qs.query, qs._db)
        related_objects = rows_to_instances(related_model, rows, qs.query, qs._db)

        # Build lookup dict by parent pk
        related_dict = {getattr(obj, f"{related_field_name}_id"): obj for obj in related_objects}

        # Assign to instances
        for instance in instances:
            related_obj = related_dict.get(instance.pk)
            setattr(instance, attr_name, related_obj)
            if not hasattr(instance._state, "fields_cache"):
                instance._state.fields_cache = {}
            instance._state.fields_cache[attr_name] = related_obj

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
