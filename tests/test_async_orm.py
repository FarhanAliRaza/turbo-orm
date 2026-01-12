"""
Comprehensive tests for turbo-orm async ORM operations.
"""

import pytest

from tests.models import Article
from turbo_orm import AsyncManager, AsyncQuerySet

# =============================================================================
# Unit Tests - No Database Required
# =============================================================================


class TestAsyncQuerySetChainableMethods:
    """Test that chainable methods return new AsyncQuerySet without DB hit."""

    def test_filter_returns_new_queryset(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1.filter(title="test")
        assert isinstance(qs2, AsyncQuerySet)
        assert qs1 is not qs2

    def test_exclude_returns_new_queryset(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1.exclude(title="test")
        assert isinstance(qs2, AsyncQuerySet)
        assert qs1 is not qs2

    def test_order_by_returns_new_queryset(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1.order_by("-id")
        assert isinstance(qs2, AsyncQuerySet)
        assert qs1 is not qs2

    def test_all_returns_new_queryset(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1.all()
        assert isinstance(qs2, AsyncQuerySet)
        assert qs1 is not qs2

    def test_distinct_returns_new_queryset(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1.distinct()
        assert isinstance(qs2, AsyncQuerySet)
        assert qs1 is not qs2

    def test_slicing_returns_new_queryset(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1[:10]
        assert isinstance(qs2, AsyncQuerySet)
        assert qs1 is not qs2

    def test_chained_operations(self):
        qs = (
            AsyncQuerySet(Article)
            .filter(is_published=True)
            .exclude(author_name="")
            .order_by("-published_at")[:10]
        )
        assert isinstance(qs, AsyncQuerySet)

    def test_query_object_is_modified(self):
        qs1 = AsyncQuerySet(Article)
        qs2 = qs1.filter(title="test")
        assert qs1.query is not qs2.query
        assert qs2.query.where


class TestAsyncManager:
    """Test AsyncManager descriptor behavior."""

    def test_manager_attached_to_model(self):
        assert hasattr(Article, "objects")
        assert isinstance(Article.objects, AsyncManager)

    def test_manager_returns_queryset(self):
        qs = Article.objects.all()
        assert isinstance(qs, AsyncQuerySet)

    def test_manager_not_accessible_via_instance(self):
        article = Article(title="test", content="test")
        with pytest.raises(AttributeError):
            article.objects

    def test_manager_filter_returns_queryset(self):
        qs = Article.objects.filter(title="test")
        assert isinstance(qs, AsyncQuerySet)

    def test_manager_exclude_returns_queryset(self):
        qs = Article.objects.exclude(title="test")
        assert isinstance(qs, AsyncQuerySet)

    def test_manager_order_by_returns_queryset(self):
        qs = Article.objects.order_by("-id")
        assert isinstance(qs, AsyncQuerySet)


# =============================================================================
# Integration Tests - Require PostgreSQL Database
# =============================================================================


class TestAsyncReadOperations:
    """Test async read operations against database."""

    @pytest.mark.asyncio
    async def test_aget_returns_single_instance(self, article_factory):
        article = await article_factory(title="Test aget")
        result = await Article.objects.aget(id=article.id)
        assert isinstance(result, Article)
        assert result.id == article.id
        assert result.title == "Test aget"

    @pytest.mark.asyncio
    async def test_aget_raises_does_not_exist(self):
        with pytest.raises(Article.DoesNotExist):
            await Article.objects.aget(id=999999)

    @pytest.mark.asyncio
    async def test_aget_raises_multiple_objects_returned(self, article_factory):
        await article_factory(title="Duplicate", author="same")
        await article_factory(title="Duplicate2", author="same")
        with pytest.raises(Article.MultipleObjectsReturned):
            await Article.objects.aget(author_name="same")

    @pytest.mark.asyncio
    async def test_afirst_returns_first_or_none(self, article_factory):
        await article_factory(title="First")
        await article_factory(title="Second")
        result = await Article.objects.order_by("id").afirst()
        assert isinstance(result, Article)
        assert result.title == "First"

    @pytest.mark.asyncio
    async def test_afirst_returns_none_when_empty(self):
        result = await Article.objects.filter(id=-1).afirst()
        assert result is None

    @pytest.mark.asyncio
    async def test_alast_returns_last_or_none(self, article_factory):
        await article_factory(title="First")
        await article_factory(title="Last")
        result = await Article.objects.order_by("id").alast()
        assert isinstance(result, Article)
        assert result.title == "Last"

    @pytest.mark.asyncio
    async def test_acount_returns_integer(self, article_factory):
        await article_factory(title="Count1")
        await article_factory(title="Count2")
        await article_factory(title="Count3")
        count = await Article.objects.filter(title__startswith="Count").acount()
        assert isinstance(count, int)
        assert count == 3

    @pytest.mark.asyncio
    async def test_aexists_returns_bool(self, article_factory):
        await article_factory(title="Exists Test")
        exists = await Article.objects.filter(title="Exists Test").aexists()
        not_exists = await Article.objects.filter(title="Does Not Exist").aexists()
        assert exists is True
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_alist_returns_list(self, article_factory):
        await article_factory(title="List1")
        await article_factory(title="List2")
        results = await Article.objects.filter(title__startswith="List").alist()
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, Article) for r in results)

    @pytest.mark.asyncio
    async def test_async_iteration(self, article_factory):
        await article_factory(title="Iter1")
        await article_factory(title="Iter2")
        await article_factory(title="Iter3")
        results = []
        async for article in Article.objects.filter(title__startswith="Iter"):
            results.append(article)
        assert len(results) == 3
        assert all(isinstance(r, Article) for r in results)

    @pytest.mark.asyncio
    async def test_filter_chain(self, article_factory):
        await article_factory(title="Chain Test", is_published=True, author="Alice")
        await article_factory(title="Chain Test 2", is_published=False, author="Bob")
        await article_factory(title="Chain Test 3", is_published=True, author="Charlie")
        results = await (
            Article.objects.filter(is_published=True).filter(title__startswith="Chain").alist()
        )
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_order_by_ascending(self, article_factory):
        await article_factory(title="Z Article", view_count=1)
        await article_factory(title="A Article", view_count=2)
        await article_factory(title="M Article", view_count=3)
        results = await Article.objects.filter(title__endswith="Article").order_by("title").alist()
        titles = [r.title for r in results]
        assert titles == ["A Article", "M Article", "Z Article"]

    @pytest.mark.asyncio
    async def test_order_by_descending(self, article_factory):
        await article_factory(title="Order1", view_count=10)
        await article_factory(title="Order2", view_count=30)
        await article_factory(title="Order3", view_count=20)
        qs = Article.objects.filter(title__startswith="Order").order_by("-view_count")
        results = await qs.alist()
        view_counts = [r.view_count for r in results]
        assert view_counts == [30, 20, 10]

    @pytest.mark.asyncio
    async def test_slice_limit(self, article_factory):
        for i in range(10):
            await article_factory(title=f"Slice{i}")
        results = await Article.objects.filter(title__startswith="Slice")[:5].alist()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_slice_offset(self, article_factory):
        for i in range(10):
            await article_factory(title=f"Offset{i}", view_count=i)
        qs = Article.objects.filter(title__startswith="Offset").order_by("view_count")[3:6]
        results = await qs.alist()
        assert len(results) == 3
        view_counts = [r.view_count for r in results]
        assert view_counts == [3, 4, 5]


class TestAsyncWriteOperations:
    """Test async write operations against database."""

    @pytest.mark.asyncio
    async def test_acreate_returns_instance_with_pk(self):
        article = await Article.objects.acreate(
            title="Created Async",
            content="Created via acreate",
            author_name="Test Author",
        )
        assert isinstance(article, Article)
        assert article.id is not None
        assert article.title == "Created Async"
        # Verify it's in the database
        fetched = await Article.objects.aget(id=article.id)
        assert fetched.title == "Created Async"

    @pytest.mark.asyncio
    async def test_aupdate_returns_count(self, article_factory):
        await article_factory(title="Update1", view_count=0)
        await article_factory(title="Update2", view_count=0)
        await article_factory(title="Other", view_count=0)
        count = await Article.objects.filter(title__startswith="Update").aupdate(view_count=100)
        assert count == 2
        results = await Article.objects.filter(title__startswith="Update").alist()
        for r in results:
            assert r.view_count == 100

    @pytest.mark.asyncio
    async def test_adelete_returns_count(self, article_factory):
        await article_factory(title="Delete1")
        await article_factory(title="Delete2")
        await article_factory(title="Keep")
        count, details = await Article.objects.filter(title__startswith="Delete").adelete()
        assert count == 2
        remaining = await Article.objects.filter(title__startswith="Delete").acount()
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_aget_or_create_creates_when_not_exists(self):
        article, created = await Article.objects.aget_or_create(
            title="GetOrCreate New",
            defaults={"content": "Default content", "author_name": "Default Author"},
        )
        assert created is True
        assert article.title == "GetOrCreate New"
        assert article.content == "Default content"

    @pytest.mark.asyncio
    async def test_aget_or_create_gets_when_exists(self, article_factory):
        existing = await article_factory(title="GetOrCreate Existing")
        article, created = await Article.objects.aget_or_create(
            title="GetOrCreate Existing",
            defaults={"content": "Should not be used"},
        )
        assert created is False
        assert article.id == existing.id

    @pytest.mark.asyncio
    async def test_abulk_create(self):
        articles = [
            Article(title="Bulk1", content="Content1"),
            Article(title="Bulk2", content="Content2"),
            Article(title="Bulk3", content="Content3"),
        ]
        created = await Article.objects.abulk_create(articles)
        assert len(created) == 3
        assert all(a.id is not None for a in created)
        count = await Article.objects.filter(title__startswith="Bulk").acount()
        assert count == 3

    @pytest.mark.asyncio
    async def test_ain_bulk(self, article_factory):
        a1 = await article_factory(title="Bulk Dict 1")
        a2 = await article_factory(title="Bulk Dict 2")
        result = await Article.objects.ain_bulk([a1.id, a2.id])
        assert isinstance(result, dict)
        assert a1.id in result
        assert a2.id in result
        assert result[a1.id].title == "Bulk Dict 1"


class TestPublicAPI:
    """Test the public API exports."""

    def test_imports(self):
        from turbo_orm import AsyncManager, AsyncQuerySet, __version__

        assert AsyncManager is not None
        assert AsyncQuerySet is not None
        assert __version__ is not None
