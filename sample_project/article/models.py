from django.db import models
from django.db.models import Manager

from turbo_orm import AsyncManager


class Article(models.Model):
    """Article model for benchmarking sync vs async."""

    title = models.CharField(max_length=255)
    content = models.TextField()
    author = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    view_count = models.IntegerField(default=0)
    is_published = models.BooleanField(default=False)

    # Django's sync manager for sync views
    objects = Manager()

    # Async manager for turbo-orm async views
    aobjects = AsyncManager()

    def __str__(self):
        return self.title
