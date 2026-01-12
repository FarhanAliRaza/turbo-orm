"""
Tests adapted from Django's async queryset tests.
Verifies turbo-orm compatibility with Django's async ORM interface.

Source: django/tests/async/test_async_queryset.py
"""

import pytest
from django.db.models import Sum

from tests.models import Article
from turbo_orm import AsyncManager


class TestAsyncQuerySetDjangoCompat:
    """Tests adapted from Django's AsyncQuerySetTest."""

    @pytest.fixture(autouse=True)
    async def setup_data(self):
        """Create test data similar to Django's setUpTestData."""
        # Clean existing data
        await Article.objects.adelete()

        # Create test articles
        self.a1 = await Article.objects.acreate(
            title="Article 1",
            content="Content 1",
            author_name="Author A",
            view_count=10,
            is_published=True,
        )
        self.a2 = await Article.objects.acreate(
            title="Article 2",
            content="Content 2",
            author_name="Author B",
            view_count=20,
            is_published=True,
        )
        self.a3 = await Article.objects.acreate(
            title="Article 3",
            content="Content 3",
            author_name="Author C",
            view_count=30,
            is_published=False,
        )
        yield

    @pytest.mark.asyncio
    async def test_async_iteration(self):
        """Test async for iteration over queryset."""
        results = []
        async for article in Article.objects.order_by("id"):
            results.append(article)
        assert len(results) == 3
        assert results[0].id == self.a1.id
        assert results[1].id == self.a2.id
        assert results[2].id == self.a3.id

    @pytest.mark.asyncio
    async def test_acount(self):
        """Test acount() returns correct count."""
        count = await Article.objects.acount()
        assert count == 3

    @pytest.mark.asyncio
    async def test_acount_filtered(self):
        """Test acount() with filter."""
        count = await Article.objects.filter(is_published=True).acount()
        assert count == 2

    @pytest.mark.asyncio
    async def test_aget(self):
        """Test aget() returns single instance."""
        instance = await Article.objects.aget(title="Article 1")
        assert instance.id == self.a1.id

    @pytest.mark.asyncio
    async def test_aget_raises_does_not_exist(self):
        """Test aget() raises DoesNotExist for no match."""
        with pytest.raises(Article.DoesNotExist):
            await Article.objects.aget(title="Nonexistent")

    @pytest.mark.asyncio
    async def test_aget_raises_multiple_objects(self):
        """Test aget() raises MultipleObjectsReturned for multiple matches."""
        with pytest.raises(Article.MultipleObjectsReturned):
            await Article.objects.aget(is_published=True)

    @pytest.mark.asyncio
    async def test_acreate(self):
        """Test acreate() creates and returns instance."""
        article = await Article.objects.acreate(
            title="New Article",
            content="New Content",
        )
        assert article.id is not None
        assert await Article.objects.acount() == 4

    @pytest.mark.asyncio
    async def test_aget_or_create_creates(self):
        """Test aget_or_create() creates when not exists."""
        instance, created = await Article.objects.aget_or_create(
            title="Created Article",
            defaults={"content": "Created Content"},
        )
        assert created is True
        assert await Article.objects.acount() == 4

    @pytest.mark.asyncio
    async def test_aget_or_create_gets(self):
        """Test aget_or_create() gets when exists."""
        instance, created = await Article.objects.aget_or_create(
            title="Article 1",
            defaults={"content": "Should not be used"},
        )
        assert created is False
        assert instance.id == self.a1.id

    @pytest.mark.asyncio
    async def test_aupdate_or_create_updates(self):
        """Test aupdate_or_create() updates existing."""
        instance, created = await Article.objects.aupdate_or_create(
            id=self.a1.id,
            defaults={"view_count": 999},
        )
        assert created is False
        assert instance.view_count == 999

    @pytest.mark.asyncio
    async def test_aupdate_or_create_creates(self):
        """Test aupdate_or_create() creates when not exists."""
        instance, created = await Article.objects.aupdate_or_create(
            title="New Title",
            defaults={"content": "New Content", "view_count": 100},
        )
        assert created is True
        assert await Article.objects.acount() == 4

    @pytest.mark.asyncio
    async def test_abulk_create(self):
        """Test abulk_create() creates multiple instances."""
        articles = [Article(title=f"Bulk {i}", content=f"Content {i}") for i in range(5)]
        created = await Article.objects.abulk_create(articles)
        assert len(created) == 5
        assert await Article.objects.acount() == 8

    @pytest.mark.asyncio
    async def test_abulk_update(self):
        """Test abulk_update() updates multiple instances."""
        articles = await Article.objects.alist()
        for article in articles:
            article.view_count = article.view_count * 10

        updated = await Article.objects.abulk_update(articles, ["view_count"])
        assert updated == 3

        # Verify updates
        a1 = await Article.objects.aget(id=self.a1.id)
        assert a1.view_count == 100

    @pytest.mark.asyncio
    async def test_ain_bulk(self):
        """Test ain_bulk() returns dict keyed by pk."""
        result = await Article.objects.ain_bulk()
        assert len(result) == 3
        assert self.a1.id in result
        assert result[self.a1.id].title == "Article 1"

    @pytest.mark.asyncio
    async def test_ain_bulk_with_ids(self):
        """Test ain_bulk() with specific IDs."""
        result = await Article.objects.ain_bulk([self.a2.id])
        assert len(result) == 1
        assert self.a2.id in result

    @pytest.mark.asyncio
    async def test_afirst(self):
        """Test afirst() returns first or None."""
        instance = await Article.objects.order_by("id").afirst()
        assert instance.id == self.a1.id

        instance = await Article.objects.filter(title="Nonexistent").afirst()
        assert instance is None

    @pytest.mark.asyncio
    async def test_alast(self):
        """Test alast() returns last or None."""
        instance = await Article.objects.order_by("id").alast()
        assert instance.id == self.a3.id

        instance = await Article.objects.filter(title="Nonexistent").alast()
        assert instance is None

    @pytest.mark.asyncio
    async def test_aaggregate(self):
        """Test aaggregate() returns aggregate values."""
        result = await Article.objects.aaggregate(total=Sum("view_count"))
        assert result == {"total": 60}

    @pytest.mark.asyncio
    async def test_aexists(self):
        """Test aexists() returns boolean."""
        exists = await Article.objects.filter(title="Article 1").aexists()
        assert exists is True

        exists = await Article.objects.filter(title="Nonexistent").aexists()
        assert exists is False

    @pytest.mark.asyncio
    async def test_aupdate(self):
        """Test aupdate() updates all matching rows."""
        count = await Article.objects.filter(is_published=True).aupdate(view_count=999)
        assert count == 2

        # Verify updates
        articles = await Article.objects.filter(is_published=True).alist()
        for article in articles:
            assert article.view_count == 999

    @pytest.mark.asyncio
    async def test_adelete(self):
        """Test adelete() deletes matching rows."""
        count, details = await Article.objects.filter(is_published=False).adelete()
        assert count == 1
        assert await Article.objects.acount() == 2

    @pytest.mark.asyncio
    async def test_alist(self):
        """Test alist() returns list of instances."""
        articles = await Article.objects.order_by("id").alist()
        assert isinstance(articles, list)
        assert len(articles) == 3
        assert articles[0].id == self.a1.id

    @pytest.mark.asyncio
    async def test_filter_chain(self):
        """Test filter chaining works correctly."""
        articles = await (
            Article.objects.filter(is_published=True).filter(view_count__gte=15).alist()
        )
        assert len(articles) == 1
        assert articles[0].id == self.a2.id

    @pytest.mark.asyncio
    async def test_exclude(self):
        """Test exclude() filters out matching rows."""
        articles = await Article.objects.exclude(is_published=False).alist()
        assert len(articles) == 2

    @pytest.mark.asyncio
    async def test_order_by(self):
        """Test order_by() orders results."""
        articles = await Article.objects.order_by("-view_count").alist()
        assert articles[0].id == self.a3.id
        assert articles[1].id == self.a2.id
        assert articles[2].id == self.a1.id

    @pytest.mark.asyncio
    async def test_slicing(self):
        """Test slicing limits results."""
        articles = await Article.objects.order_by("id")[:2].alist()
        assert len(articles) == 2
        assert articles[0].id == self.a1.id
        assert articles[1].id == self.a2.id

    @pytest.mark.asyncio
    async def test_slicing_offset(self):
        """Test slicing with offset."""
        articles = await Article.objects.order_by("id")[1:3].alist()
        assert len(articles) == 2
        assert articles[0].id == self.a2.id
        assert articles[1].id == self.a3.id


class TestAsyncManagerIntegration:
    """Test AsyncManager behaves like Django's manager."""

    def test_manager_is_async_manager(self):
        """Verify our manager is an AsyncManager."""
        assert isinstance(Article.objects, AsyncManager)

    def test_manager_not_accessible_from_instance(self):
        """Manager should not be accessible from model instance."""
        article = Article(title="Test")
        with pytest.raises(AttributeError):
            article.objects

    def test_chainable_methods_return_queryset(self):
        """Chainable methods should return queryset without DB hit."""
        from turbo_orm import AsyncQuerySet

        qs = Article.objects.filter(is_published=True)
        assert isinstance(qs, AsyncQuerySet)

        qs = qs.exclude(view_count=0)
        assert isinstance(qs, AsyncQuerySet)

        qs = qs.order_by("-id")
        assert isinstance(qs, AsyncQuerySet)

        qs = qs[:10]
        assert isinstance(qs, AsyncQuerySet)
