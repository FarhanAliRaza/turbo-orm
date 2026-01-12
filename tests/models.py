"""
Test models for turbo-orm.
"""

from django.db import models

from turbo_orm import AsyncManager, AsyncModelMixin


class Author(AsyncModelMixin, models.Model):
    """Test model for ForeignKey relationships (select_related)."""

    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)

    objects = AsyncManager()

    class Meta:
        app_label = "tests"

    def __str__(self):
        return self.name


class Category(models.Model):
    """Test model for ManyToMany relationships (prefetch_related)."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    objects = AsyncManager()

    class Meta:
        app_label = "tests"

    def __str__(self):
        return self.name


class Article(AsyncModelMixin, models.Model):
    """Test model for async ORM operations."""

    title = models.CharField(max_length=255)
    content = models.TextField(default="")
    author_name = models.CharField(max_length=100, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)

    # ForeignKey for select_related testing
    author = models.ForeignKey(
        Author,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )

    # ManyToMany for prefetch_related testing
    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name="articles",
    )

    objects = AsyncManager()

    class Meta:
        app_label = "tests"

    def __str__(self):
        return self.title


class Comment(AsyncModelMixin, models.Model):
    """Test model for reverse ForeignKey relationships."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AsyncManager()

    class Meta:
        app_label = "tests"

    def __str__(self):
        return f"Comment on {self.article_id}"
