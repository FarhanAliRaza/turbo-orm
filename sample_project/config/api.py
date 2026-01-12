"""
Django Bolt API - Benchmark sync vs async ORM

Endpoints:
- /sync   - 8 queries sequential (Django sync ORM)
- /django - 8 queries concurrent (Django async - uses sync_to_async)
- /async  - 8 queries concurrent (turbo-orm - native async)
- /seed   - Seed database with test data
"""

import asyncio

from django_bolt import BoltAPI

from article.models import Article

api = BoltAPI()


@api.get("/sync")
def bench_sync():
    """Benchmark: 8 queries sequential using sync ORM."""
    total = Article.objects.count()
    published = Article.objects.filter(is_published=True).count()
    latest = list(Article.objects.order_by("-id")[:10])
    popular = list(Article.objects.order_by("-view_count")[:5])
    search_results = list(Article.objects.filter(title__icontains="Article 1")[:10])
    by_author = list(Article.objects.filter(author="Author 1")[:10])
    first = Article.objects.first()
    exists = Article.objects.filter(view_count__gt=5000).exists()

    return {
        "total": total,
        "published": published,
        "latest": [a.id for a in latest],
        "popular": [a.id for a in popular],
        "search": len(search_results),
        "by_author": len(by_author),
        "first_id": first.id if first else None,
        "high_views_exist": exists,
    }


async def alist(qs):
    """Django doesn't have alist(), so we use async comprehension."""
    return [obj async for obj in qs]


@api.get("/django")
async def bench_django():
    """Benchmark: 8 queries concurrent using Django async (sync_to_async)."""
    (
        total,
        published,
        latest,
        popular,
        search_results,
        by_author,
        first,
        exists,
    ) = await asyncio.gather(
        Article.objects.acount(),
        Article.objects.filter(is_published=True).acount(),
        alist(Article.objects.order_by("-id")[:10]),
        alist(Article.objects.order_by("-view_count")[:5]),
        alist(Article.objects.filter(title__icontains="Article 1")[:10]),
        alist(Article.objects.filter(author="Author 1")[:10]),
        Article.objects.afirst(),
        Article.objects.filter(view_count__gt=5000).aexists(),
    )

    return {
        "total": total,
        "published": published,
        "latest": [a.id for a in latest],
        "popular": [a.id for a in popular],
        "search": len(search_results),
        "by_author": len(by_author),
        "first_id": first.id if first else None,
        "high_views_exist": exists,
    }


@api.get("/async")
async def bench_async():
    """Benchmark: 8 queries concurrent using turbo-orm (native async)."""
    (
        total,
        published,
        latest,
        popular,
        search_results,
        by_author,
        first,
        exists,
    ) = await asyncio.gather(
        Article.aobjects.acount(),
        Article.aobjects.filter(is_published=True).acount(),
        Article.aobjects.order_by("-id")[:10].alist(),
        Article.aobjects.order_by("-view_count")[:5].alist(),
        Article.aobjects.filter(title__icontains="Article 1")[:10].alist(),
        Article.aobjects.filter(author="Author 1")[:10].alist(),
        Article.aobjects.afirst(),
        Article.aobjects.filter(view_count__gt=5000).aexists(),
    )

    return {
        "total": total,
        "published": published,
        "latest": [a.id for a in latest],
        "popular": [a.id for a in popular],
        "search": len(search_results),
        "by_author": len(by_author),
        "first_id": first.id if first else None,
        "high_views_exist": exists,
    }


@api.get("/seed")
async def seed():
    """Seed the database with test articles."""
    articles = [
        Article(
            title=f"Article {i}",
            content=f"Content for article {i}",
            author=f"Author {i % 10}",
            is_published=i % 5 != 0,
            view_count=i * 10,
        )
        for i in range(1000)
    ]
    created = await Article.aobjects.abulk_create(articles)
    return {"created": len(created)}
