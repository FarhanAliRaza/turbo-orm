"""
turbo-orm
=========

True async ORM for Django - bridges Django's ORM with async database backends
for genuine async database operations without thread pool overhead.

Requirements:
    - Python 3.12+
    - Django 4.2+
    - PostgreSQL with psycopg3
    - django-async-backend

Installation:
    pip install turbo-orm

Basic Usage::

    from django.db import models
    from turbo_orm import AsyncManager

    class User(models.Model):
        username = models.CharField(max_length=150)
        email = models.EmailField()
        is_active = models.BooleanField(default=True)

        # Add async manager - replaces Django's default manager
        objects = AsyncManager()

    # In async views
    async def get_users(request):
        # Chainable (lazy, no DB hit)
        qs = User.objects.filter(is_active=True).order_by('-id')[:10]

        # Terminal (true async DB hit)
        users = await qs.alist()

        # Or iterate
        async for user in qs:
            print(user.username)

        # Single object
        user = await User.objects.aget(id=1)

        # Count
        count = await User.objects.filter(is_active=True).acount()

        # Create
        new_user = await User.objects.acreate(
            username='test',
            email='test@example.com'
        )
"""

__version__ = "0.5.0"

from turbo_orm.exceptions import EmptyResultSet, TurboOrmError
from turbo_orm.manager import AsyncManager
from turbo_orm.models import AsyncModelMixin
from turbo_orm.queryset import AsyncQuerySet

__all__ = [
    "__version__",
    "AsyncManager",
    "AsyncModelMixin",
    "AsyncQuerySet",
    "TurboOrmError",
    "EmptyResultSet",
]
