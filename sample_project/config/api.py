"""
Django Bolt Benchmark API - Comparing ORM approaches

3 main endpoints with identical logic:
1. /sync      - Django sync ORM
2. /django    - Django's fake async (sync_to_async under the hood)
3. /async     - Turbo-orm true async (no thread pool)
"""

from django_bolt import BoltAPI

from article.models import Article

api = BoltAPI()


def serialize_article(article):
    return {
        "id": article.id,
        "title": article.title,
        "author": article.author,
        "view_count": article.view_count,
    }


@api.get("/sync")
def sync_read():
    """Read using Django's sync ORM."""
    articles = list(Article.objects.all()[:100])
    count = Article.objects.count()
    for article in articles[:10]:
        _ = Article.objects.get(id=article.id)
    return {
        "type": "sync",
        "count": count,
        "articles": [serialize_article(a) for a in articles],
    }


@api.get("/django")
async def django_async_read():
    """Read using Django's async ORM (sync_to_async under the hood)."""
    articles = [a async for a in Article.objects.all()[:100]]
    count = await Article.objects.acount()
    for article in articles[:10]:
        _ = await Article.objects.aget(id=article.id)
    return {
        "type": "django_fake_async",
        "count": count,
        "articles": [serialize_article(a) for a in articles],
    }


@api.get("/async")
async def turbo_async_read():
    """Read using turbo-orm's true async (no thread pool overhead)."""
    articles = await Article.objects.all()[:100].alist()
    count = await Article.objects.acount()
    for article in articles[:10]:
        _ = await Article.objects.aget(id=article.id)
    return {
        "type": "turbo_orm_async",
        "count": count,
        "articles": [serialize_article(a) for a in articles],
    }


@api.get("/seed")
async def seed():
    """Seed the database with test articles."""
    articles = [
        Article(
            title=f"Article {i}",
            content=f"Content {i}",
            author=f"Author {i % 10}",
            is_published=i % 2 == 0,
            view_count=i * 10,
        )
        for i in range(1000)
    ]
    created = await Article.aobjects.abulk_create(articles)
    return {"created": len(created)}
