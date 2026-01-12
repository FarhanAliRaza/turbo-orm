"""
Benchmark views comparing sync vs async database operations.

Run the server and use:
    curl http://localhost:8000/sync/read
    curl http://localhost:8000/async/read
    curl http://localhost:8000/sync/write
    curl http://localhost:8000/async/write
"""

import time
import uuid

from django.http import JsonResponse

from article.models import Article


# =============================================================================
# Sync Views (using Django's default sync manager)
# =============================================================================


def sync_read_view(request):
    """Sync view: read multiple articles using Django's sync ORM."""
    start = time.perf_counter()

    # Fetch articles (using Django's sync manager)
    articles = list(Article.objects.all()[:100])
    count = Article.objects.count()

    # Fetch individual articles
    for article in articles[:10]:
        _ = Article.objects.get(id=article.id)

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "sync",
        "operation": "read",
        "articles_fetched": len(articles),
        "total_count": count,
        "elapsed_ms": round(elapsed * 1000, 2),
    })


def sync_write_view(request):
    """Sync view: create multiple articles using Django's sync ORM."""
    start = time.perf_counter()

    # Create articles
    created = []
    for i in range(10):
        article = Article.objects.create(
            title=f"Sync Article {uuid.uuid4().hex[:8]}",
            content=f"Content for sync article {i}",
            author="Sync Author",
            is_published=True,
        )
        created.append(article.id)

    # Update articles
    Article.objects.filter(id__in=created).update(view_count=100)

    # Delete articles
    deleted_count, _ = Article.objects.filter(id__in=created).delete()

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "sync",
        "operation": "write",
        "created": len(created),
        "deleted": deleted_count,
        "elapsed_ms": round(elapsed * 1000, 2),
    })


# =============================================================================
# Async Views (using turbo-orm's true async via aobjects)
# =============================================================================


async def async_read_view(request):
    """Async view: read multiple articles using turbo-orm."""
    start = time.perf_counter()

    # Fetch articles (using turbo-orm async manager)
    articles = await Article.aobjects.all()[:100].alist()
    count = await Article.aobjects.acount()

    # Fetch individual articles
    for article in articles[:10]:
        _ = await Article.aobjects.aget(id=article.id)

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "async",
        "operation": "read",
        "articles_fetched": len(articles),
        "total_count": count,
        "elapsed_ms": round(elapsed * 1000, 2),
    })


async def async_write_view(request):
    """Async view: create multiple articles using turbo-orm."""
    start = time.perf_counter()

    # Create articles
    created = []
    for i in range(10):
        article = await Article.aobjects.acreate(
            title=f"Async Article {uuid.uuid4().hex[:8]}",
            content=f"Content for async article {i}",
            author="Async Author",
            is_published=True,
        )
        created.append(article.id)

    # Update articles
    await Article.aobjects.filter(id__in=created).aupdate(view_count=100)

    # Delete articles
    deleted_count, _ = await Article.aobjects.filter(id__in=created).adelete()

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "async",
        "operation": "write",
        "created": len(created),
        "deleted": deleted_count,
        "elapsed_ms": round(elapsed * 1000, 2),
    })


# =============================================================================
# Django's "Fake Async" (sync_to_async under the hood)
# =============================================================================


async def django_async_read_view(request):
    """Django's built-in async - uses sync_to_async (thread pool)."""
    start = time.perf_counter()

    # Django's async methods - wraps sync in thread pool
    articles = [a async for a in Article.objects.all()[:100]]
    count = await Article.objects.acount()

    for article in articles[:10]:
        _ = await Article.objects.aget(id=article.id)

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "django_fake_async",
        "operation": "read",
        "articles_fetched": len(articles),
        "total_count": count,
        "elapsed_ms": round(elapsed * 1000, 2),
    })


async def django_async_write_view(request):
    """Django's built-in async - uses sync_to_async (thread pool)."""
    start = time.perf_counter()

    created = []
    for i in range(10):
        article = await Article.objects.acreate(
            title=f"Django Async {uuid.uuid4().hex[:8]}",
            content=f"Content {i}",
            author="Django Author",
            is_published=True,
        )
        created.append(article.id)

    await Article.objects.filter(id__in=created).aupdate(view_count=100)
    deleted_count, _ = await Article.objects.filter(id__in=created).adelete()

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "django_fake_async",
        "operation": "write",
        "created": len(created),
        "deleted": deleted_count,
        "elapsed_ms": round(elapsed * 1000, 2),
    })


# =============================================================================
# Concurrent fetch test - this is where async shines
# =============================================================================


def sync_concurrent_view(request):
    """Sync view: fetch 10 articles sequentially (can't parallelize)."""
    import random
    start = time.perf_counter()

    # Get 10 random IDs
    all_ids = list(Article.objects.values_list("id", flat=True)[:100])
    ids_to_fetch = random.sample(all_ids, min(10, len(all_ids)))

    # Fetch sequentially - sync can't parallelize DB calls
    articles = []
    for article_id in ids_to_fetch:
        articles.append(Article.objects.get(id=article_id))

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "sync_sequential",
        "fetched": len(articles),
        "elapsed_ms": round(elapsed * 1000, 2),
    })


async def async_concurrent_view(request):
    """Async view: fetch 10 articles concurrently using asyncio.gather."""
    import asyncio
    import random
    start = time.perf_counter()

    # Get 10 random IDs (use sync objects for this simple query, or get articles first)
    all_articles = await Article.aobjects.all()[:100].alist()
    ids_to_fetch = random.sample([a.id for a in all_articles], min(10, len(all_articles)))

    # Fetch concurrently - async can parallelize DB calls!
    articles = await asyncio.gather(*[
        Article.aobjects.aget(id=article_id)
        for article_id in ids_to_fetch
    ])

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "type": "async_concurrent",
        "fetched": len(articles),
        "elapsed_ms": round(elapsed * 1000, 2),
    })


# =============================================================================
# Seed data view
# =============================================================================


async def debug_view(request):
    """Debug view to verify async backend is being used."""
    from django_async_backend.db import async_connections
    from django.db import connections

    info = {}

    # Check sync connection
    sync_conn = connections["default"]
    info["sync_engine"] = sync_conn.settings_dict["ENGINE"]

    # Check async connection
    async_conn = async_connections["default"]
    info["async_conn_type"] = type(async_conn).__name__
    info["async_conn_module"] = type(async_conn).__module__

    # Execute a real async query and check cursor type
    async with async_connections["default"].cursor() as cursor:
        info["cursor_type"] = type(cursor).__name__
        info["cursor_module"] = type(cursor).__module__
        await cursor.execute("SELECT 1")
        row = await cursor.fetchone()
        info["query_result"] = row[0]

    # Verify turbo-orm uses async
    from turbo_orm.execution import execute_query
    from django.db.models.sql import Query
    from article.models import Article

    query = Query(Article)
    query.set_limits(0, 1)
    rows = await execute_query(query, "default")
    info["turbo_orm_works"] = len(rows) >= 0
    info["turbo_orm_row_count"] = len(rows)

    return JsonResponse(info)


async def seed_view(request):
    """Seed the database with test articles."""
    start = time.perf_counter()

    articles = [
        Article(
            title=f"Article {i}",
            content=f"This is the content for article {i}. " * 10,
            author=f"Author {i % 10}",
            is_published=i % 2 == 0,
            view_count=i * 10,
        )
        for i in range(1000)
    ]

    created = await Article.aobjects.abulk_create(articles)

    elapsed = time.perf_counter() - start

    return JsonResponse({
        "operation": "seed",
        "created": len(created),
        "elapsed_ms": round(elapsed * 1000, 2),
    })
