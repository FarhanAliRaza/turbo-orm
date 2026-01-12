"""
Pytest configuration for turbo-orm tests.
"""

import os
import sys

# Add project root and src to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

import django  # noqa: E402
import pytest  # noqa: E402
from django.conf import settings  # noqa: E402


def pytest_configure():
    """Configure Django settings for tests."""
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                "default": {
                    "ENGINE": "django_async_backend.db.backends.postgresql",
                    "NAME": os.environ.get("POSTGRES_DB", "turbo_orm_test"),
                    "USER": os.environ.get("POSTGRES_USER", "postgres"),
                    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
                    "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
                    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django_async_backend",
                "turbo_orm",
                "tests",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            SECRET_KEY="test-secret-key",
        )
        django.setup()


@pytest.fixture
def article_factory():
    """Factory for creating Article instances - returns an async function."""
    from tests.models import Article

    async def create_article(title="Test Article", content="Test content", **kwargs):
        return await Article.objects.acreate(
            title=title,
            content=content,
            author=kwargs.get("author", ""),
            is_published=kwargs.get("is_published", False),
            view_count=kwargs.get("view_count", 0),
        )

    return create_article


@pytest.fixture
def category_factory():
    """Factory for creating Category instances - returns an async function."""
    from tests.models import Category

    async def create_category(name="Test Category", description=""):
        return await Category.objects.acreate(name=name, description=description)

    return create_category


@pytest.fixture(autouse=True)
async def clean_tables():
    """Clean tables before each test."""
    from django_async_backend.db import async_connections

    async with async_connections["default"].cursor() as cursor:
        await cursor.execute("TRUNCATE tests_article RESTART IDENTITY CASCADE")
        await cursor.execute("TRUNCATE tests_category RESTART IDENTITY CASCADE")
    yield
