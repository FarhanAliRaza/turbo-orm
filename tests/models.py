"""
Test models for turbo-orm.
"""

from django.db import models

from turbo_orm import AsyncManager


class Article(models.Model):
    """Test model for async ORM operations."""

    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.CharField(max_length=100, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)

    # Async manager for true async operations (use 'objects' to avoid Django's default manager)
    objects = AsyncManager()

    class Meta:
        app_label = "tests"

    def __str__(self):
        return self.title


class Category(models.Model):
    """Test model for relationships."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    objects = AsyncManager()

    class Meta:
        app_label = "tests"

    def __str__(self):
        return self.name
