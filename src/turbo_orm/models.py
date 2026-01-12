"""
Async Model Mixin - Provides async instance methods for Django models.

Usage:
    from turbo_orm import AsyncModelMixin

    class Article(AsyncModelMixin, models.Model):
        title = models.CharField(max_length=200)

    # Then use:
    article = Article(title="Test")
    await article.asave()
    await article.arefresh_from_db()
    await article.adelete()
"""

from typing import TYPE_CHECKING, Optional

from django.db.models import Q

if TYPE_CHECKING:
    pass


class AsyncModelMixin:
    """
    Mixin that provides async save, delete, and refresh methods for Django models.

    Inherit from this mixin before models.Model:
        class MyModel(AsyncModelMixin, models.Model):
            ...
    """

    async def asave(
        self,
        update_fields: Optional[list[str]] = None,
        using: str = "default",
    ) -> None:
        """
        Async save model instance to database.

        Args:
            update_fields: List of field names to update. If None and updating,
                          all non-pk fields are updated.
            using: Database alias.
        """
        from turbo_orm.execution import execute_insert, execute_instance_save

        if self._state.adding:
            await execute_insert(self, using)
        else:
            if update_fields is None:
                update_fields = [
                    f.name for f in self._meta.concrete_fields if not f.primary_key
                ]
            if update_fields:
                await execute_instance_save(self, update_fields, using)

    async def adelete(self, using: str = "default") -> tuple[int, dict[str, int]]:
        """
        Async delete model instance from database.

        Args:
            using: Database alias.

        Returns:
            Tuple of (number deleted, {model_label: count})
        """
        from django.db.models.sql import Query

        from turbo_orm.execution import execute_delete

        query = Query(self.__class__)
        query.add_q(Q(pk=self.pk))
        count, deleted = await execute_delete(query, using)

        # Clear pk to indicate instance is deleted
        self.pk = None
        self._state.adding = True

        return count, deleted

    async def arefresh_from_db(
        self,
        using: str = "default",
        fields: Optional[list[str]] = None,
    ) -> None:
        """
        Async reload field values from the database.

        Args:
            using: Database alias.
            fields: List of field names to refresh. If None, all fields are refreshed.
        """
        from turbo_orm.execution import execute_query

        # Build query for this instance
        query = self.__class__._default_manager.all().query.clone()
        query.add_q(Q(pk=self.pk))

        if fields:
            # Defer all fields except the ones we want to refresh
            defer_fields = [
                f.name for f in self._meta.concrete_fields
                if f.name not in fields and not f.primary_key
            ]
            if defer_fields:
                query.add_deferred_loading(defer_fields)

        rows = await execute_query(query, using)

        if not rows:
            raise self.__class__.DoesNotExist(
                f"{self.__class__.__name__} matching query does not exist."
            )

        row = rows[0]

        # Get field names - use concrete fields in order
        concrete_fields = self._meta.concrete_fields
        if fields:
            # Only update requested fields + pk
            field_names = [f.attname for f in concrete_fields if f.name in fields or f.primary_key]
        else:
            field_names = [f.attname for f in concrete_fields]

        # Update instance fields
        for i, field_name in enumerate(field_names):
            if i < len(row) and hasattr(self, field_name):
                setattr(self, field_name, row[i])
