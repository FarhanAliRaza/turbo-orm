"""
AsyncManager - Manager that provides async database access for Django models.

Inherits from Django's BaseManager so it's properly recognized by Django's
metaclass, but overrides methods to return AsyncQuerySet for true async ops.
"""

from typing import TYPE_CHECKING, Any, Optional, TypeVar

from django.db.models.manager import BaseManager

if TYPE_CHECKING:
    from django.db.models import Model
    from turbo_orm.queryset import AsyncQuerySet

T = TypeVar("T", bound="Model")


class AsyncManager(BaseManager.from_queryset(type("_EmptyQS", (), {}))):  # type: ignore
    """
    Async manager for Django models.

    Inherits from Django's BaseManager so it's recognized by the model metaclass,
    but returns AsyncQuerySet instances for true async database operations.

    Example:
        class User(models.Model):
            username = models.CharField(max_length=150)
            objects = AsyncManager()

        # Usage
        user = await User.objects.aget(id=1)
        users = await User.objects.filter(is_active=True).alist()
    """

    def __init__(self) -> None:
        """Initialize AsyncManager."""
        super().__init__()
        self._db: str = "default"

    def get_queryset(self) -> "AsyncQuerySet[T]":
        """
        Return a new AsyncQuerySet for this manager's model.

        Override this method in subclasses to customize the base queryset.

        Returns:
            New AsyncQuerySet instance
        """
        from turbo_orm.queryset import AsyncQuerySet

        return AsyncQuerySet(model=self.model, using=self._db)

    def using(self, alias: str) -> "AsyncManager[T]":
        """
        Return a manager using the specified database.

        Args:
            alias: Database alias

        Returns:
            New manager using the specified database
        """
        clone = self.__class__()
        clone.model = self.model
        clone.name = self.name
        clone._db = alias
        return clone

    # =========================================================================
    # Chainable methods - delegate to queryset
    # =========================================================================

    def all(self) -> "AsyncQuerySet[T]":
        """Return all objects."""
        return self.get_queryset().all()

    def filter(self, *args: Any, **kwargs: Any) -> "AsyncQuerySet[T]":
        """Filter objects by the given conditions."""
        return self.get_queryset().filter(*args, **kwargs)

    def exclude(self, *args: Any, **kwargs: Any) -> "AsyncQuerySet[T]":
        """Exclude objects matching the given conditions."""
        return self.get_queryset().exclude(*args, **kwargs)

    def order_by(self, *fields: str) -> "AsyncQuerySet[T]":
        """Order objects by the given fields."""
        return self.get_queryset().order_by(*fields)

    def distinct(self, *fields: str) -> "AsyncQuerySet[T]":
        """Return distinct objects."""
        return self.get_queryset().distinct(*fields)

    def select_related(self, *fields: str) -> "AsyncQuerySet[T]":
        """Select related objects via JOIN."""
        return self.get_queryset().select_related(*fields)

    def prefetch_related(self, *lookups: Any) -> "AsyncQuerySet[T]":
        """Prefetch related objects."""
        return self.get_queryset().prefetch_related(*lookups)

    def only(self, *fields: str) -> "AsyncQuerySet[T]":
        """Load only the specified fields."""
        return self.get_queryset().only(*fields)

    def defer(self, *fields: str) -> "AsyncQuerySet[T]":
        """Defer loading of the specified fields."""
        return self.get_queryset().defer(*fields)

    def values(self, *fields: str, **expressions: Any) -> "AsyncQuerySet[T]":
        """Return dictionaries instead of model instances."""
        return self.get_queryset().values(*fields, **expressions)

    def values_list(
        self, *fields: str, flat: bool = False, named: bool = False
    ) -> "AsyncQuerySet[T]":
        """Return tuples instead of model instances."""
        return self.get_queryset().values_list(*fields, flat=flat, named=named)

    def annotate(self, *args: Any, **kwargs: Any) -> "AsyncQuerySet[T]":
        """Add annotations to the queryset."""
        return self.get_queryset().annotate(*args, **kwargs)

    # =========================================================================
    # Async terminal methods - delegate to queryset
    # =========================================================================

    async def aget(self, *args: Any, **kwargs: Any) -> T:
        """Get a single object matching the filters."""
        return await self.get_queryset().aget(*args, **kwargs)

    async def afirst(self) -> Optional[T]:
        """Get the first object or None."""
        return await self.get_queryset().afirst()

    async def alast(self) -> Optional[T]:
        """Get the last object or None."""
        return await self.get_queryset().alast()

    async def acount(self) -> int:
        """Return the count of objects."""
        return await self.get_queryset().acount()

    async def aexists(self) -> bool:
        """Return True if any objects exist."""
        return await self.get_queryset().aexists()

    async def alist(self) -> list[T]:
        """Return all objects as a list."""
        return await self.get_queryset().alist()

    async def acreate(self, **kwargs: Any) -> T:
        """Create and return a new object."""
        return await self.get_queryset().acreate(**kwargs)

    async def aupdate(self, **kwargs: Any) -> int:
        """Update all objects with the given values."""
        return await self.get_queryset().aupdate(**kwargs)

    async def adelete(self) -> tuple[int, dict[str, int]]:
        """Delete all objects."""
        return await self.get_queryset().adelete()

    async def abulk_create(
        self,
        objs: list[T],
        batch_size: Optional[int] = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Optional[list[str]] = None,
        unique_fields: Optional[list[str]] = None,
    ) -> list[T]:
        """Bulk create objects."""
        return await self.get_queryset().abulk_create(
            objs,
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
        """Bulk update objects."""
        return await self.get_queryset().abulk_update(
            objs, fields, batch_size=batch_size
        )

    async def aget_or_create(
        self,
        defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[T, bool]:
        """Get or create an object."""
        return await self.get_queryset().aget_or_create(defaults=defaults, **kwargs)

    async def aupdate_or_create(
        self,
        defaults: Optional[dict[str, Any]] = None,
        create_defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> tuple[T, bool]:
        """Update or create an object."""
        return await self.get_queryset().aupdate_or_create(
            defaults=defaults, create_defaults=create_defaults, **kwargs
        )

    async def ain_bulk(
        self,
        id_list: Optional[list[Any]] = None,
        *,
        field_name: str = "pk",
    ) -> dict[Any, T]:
        """Return objects keyed by their ID."""
        return await self.get_queryset().ain_bulk(id_list, field_name=field_name)

    async def aaggregate(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Return aggregate values."""
        return await self.get_queryset().aaggregate(*args, **kwargs)

    # =========================================================================
    # Utility methods
    # =========================================================================

    def __repr__(self) -> str:
        model_name = self.model.__name__ if self.model else "unbound"
        return f"<AsyncManager [{model_name}]>"

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def db(self) -> str:
        """Return the database alias."""
        return self._db
