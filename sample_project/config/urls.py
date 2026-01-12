from django.contrib import admin
from django.urls import path

from article.views import (
    async_concurrent_view,
    async_read_view,
    async_write_view,
    django_async_read_view,
    django_async_write_view,
    seed_view,
    sync_concurrent_view,
    sync_read_view,
    sync_write_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Sync endpoints
    path("sync/read", sync_read_view, name="sync_read"),
    path("sync/write", sync_write_view, name="sync_write"),
    # Async endpoints
    path("async/read", async_read_view, name="async_read"),
    path("async/write", async_write_view, name="async_write"),
    # Django's fake async (sync_to_async)
    path("django/read", django_async_read_view, name="django_read"),
    path("django/write", django_async_write_view, name="django_write"),
    # Concurrent benchmark
    path("sync/concurrent", sync_concurrent_view, name="sync_concurrent"),
    path("async/concurrent", async_concurrent_view, name="async_concurrent"),
    # Utility
    path("seed", seed_view, name="seed"),
]
