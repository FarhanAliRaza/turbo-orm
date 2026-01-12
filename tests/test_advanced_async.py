"""
Advanced tests for turbo-orm - model methods, relationships, and additional operations.

Tests adapted from Django's async test suite.
"""

import pytest
from django.db.models import Sum

from tests.models import Article, Author, Comment
from turbo_orm import AsyncModelMixin

# =============================================================================
# AsyncModelMixin Tests (asave, adelete, arefresh_from_db)
# =============================================================================


class TestAsyncModelMixin:
    """Test AsyncModelMixin instance methods."""

    def test_model_inherits_mixin(self):
        """Verify models inherit from AsyncModelMixin."""
        assert issubclass(Article, AsyncModelMixin)
        assert issubclass(Author, AsyncModelMixin)
        assert issubclass(Comment, AsyncModelMixin)

    @pytest.mark.asyncio
    async def test_asave_creates_new_instance(self):
        """Test asave() for creating a new instance."""
        article = Article(title="New Article", content="Content")
        assert article.pk is None

        await article.asave()

        assert article.pk is not None
        # Verify in database
        fetched = await Article.objects.aget(pk=article.pk)
        assert fetched.title == "New Article"

    @pytest.mark.asyncio
    async def test_asave_updates_existing_instance(self, article_factory):
        """Test asave() for updating an existing instance."""
        article = await article_factory(title="Original Title")
        original_pk = article.pk

        article.title = "Updated Title"
        await article.asave()

        assert article.pk == original_pk
        fetched = await Article.objects.aget(pk=article.pk)
        assert fetched.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_asave_with_update_fields(self, article_factory):
        """Test asave() with specific update_fields."""
        article = await article_factory(title="Title", view_count=10)

        article.title = "New Title"
        article.view_count = 999
        await article.asave(update_fields=["title"])

        fetched = await Article.objects.aget(pk=article.pk)
        assert fetched.title == "New Title"
        assert fetched.view_count == 10  # Should not be updated

    @pytest.mark.asyncio
    async def test_adelete_removes_instance(self, article_factory):
        """Test adelete() removes instance from database."""
        article = await article_factory(title="To Delete")
        pk = article.pk

        count, details = await article.adelete()

        assert count == 1
        assert article.pk is None
        with pytest.raises(Article.DoesNotExist):
            await Article.objects.aget(pk=pk)

    @pytest.mark.asyncio
    async def test_arefresh_from_db(self, article_factory):
        """Test arefresh_from_db() reloads data from database."""
        article = await article_factory(title="Original")

        # Update in DB directly
        await Article.objects.filter(pk=article.pk).aupdate(title="Updated in DB")

        # Instance still has old value
        assert article.title == "Original"

        # Refresh from DB
        await article.arefresh_from_db()

        assert article.title == "Updated in DB"

    @pytest.mark.asyncio
    async def test_arefresh_from_db_with_fields(self, article_factory):
        """Test arefresh_from_db() with specific fields."""
        article = await article_factory(title="Title", view_count=10)

        await Article.objects.filter(pk=article.pk).aupdate(title="New Title", view_count=999)

        # Only refresh title
        await article.arefresh_from_db(fields=["title"])

        assert article.title == "New Title"
        # view_count was not refreshed, so it keeps old value
        assert article.view_count == 10

    @pytest.mark.asyncio
    async def test_arefresh_from_db_deleted_raises(self, article_factory):
        """Test arefresh_from_db() raises DoesNotExist for deleted instance."""
        article = await article_factory(title="Will Delete")
        pk = article.pk

        await Article.objects.filter(pk=pk).adelete()

        with pytest.raises(Article.DoesNotExist):
            await article.arefresh_from_db()


# =============================================================================
# select_related Tests
# =============================================================================


class TestSelectRelated:
    """Test select_related functionality for ForeignKey relationships."""

    @pytest.mark.asyncio
    async def test_select_related_loads_fk(self, author_factory, article_factory):
        """Test select_related() loads ForeignKey in single query."""
        author = await author_factory(name="Jane Doe")
        await article_factory(title="Test Article", author_obj=author)

        articles = await Article.objects.select_related("author").alist()

        assert len(articles) == 1
        assert articles[0].author is not None
        assert articles[0].author.name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_select_related_null_fk(self, article_factory):
        """Test select_related() with NULL ForeignKey."""
        await article_factory(title="No Author")

        articles = await Article.objects.select_related("author").alist()

        assert len(articles) == 1
        assert articles[0].author is None

    @pytest.mark.asyncio
    async def test_select_related_with_filter(self, author_factory, article_factory):
        """Test select_related() combined with filter()."""
        author = await author_factory(name="Author A")
        await article_factory(title="Article 1", author_obj=author)
        await article_factory(title="Article 2", author_obj=None)

        articles = await (
            Article.objects.select_related("author").filter(author__isnull=False).alist()
        )

        assert len(articles) == 1
        assert articles[0].author.name == "Author A"

    @pytest.mark.asyncio
    async def test_aget_with_select_related(self, author_factory, article_factory):
        """Test aget() with select_related()."""
        author = await author_factory(name="Test Author")
        article = await article_factory(title="Single Article", author_obj=author)

        fetched = await Article.objects.select_related("author").aget(pk=article.pk)

        assert fetched.author is not None
        assert fetched.author.name == "Test Author"


# =============================================================================
# prefetch_related Tests
# =============================================================================


class TestPrefetchRelated:
    """Test prefetch_related functionality for reverse FK and M2M."""

    @pytest.mark.asyncio
    async def test_prefetch_related_reverse_fk(self, article_factory, comment_factory):
        """Test prefetch_related() for reverse ForeignKey."""
        article = await article_factory(title="Article with Comments")
        await comment_factory(article=article, text="Comment 1")
        await comment_factory(article=article, text="Comment 2")

        articles = await Article.objects.prefetch_related("comments").alist()

        assert len(articles) == 1
        assert hasattr(articles[0], "_prefetched_objects_cache")
        comments = articles[0]._prefetched_objects_cache.get("comments", [])
        assert len(comments) == 2
        assert {c.text for c in comments} == {"Comment 1", "Comment 2"}

    @pytest.mark.asyncio
    async def test_prefetch_related_empty(self, article_factory):
        """Test prefetch_related() with no related objects."""
        await article_factory(title="No Comments")

        articles = await Article.objects.prefetch_related("comments").alist()

        assert len(articles) == 1
        comments = articles[0]._prefetched_objects_cache.get("comments", [])
        assert comments == []

    @pytest.mark.asyncio
    async def test_prefetch_related_forward_fk(self, author_factory, article_factory):
        """Test prefetch_related() for forward ForeignKey."""
        author = await author_factory(name="Prefetch Author")
        await article_factory(title="Article", author_obj=author)

        articles = await Article.objects.prefetch_related("author").alist()

        assert len(articles) == 1
        assert articles[0].author is not None
        assert articles[0].author.name == "Prefetch Author"


# =============================================================================
# abulk_update Tests
# =============================================================================


class TestBulkUpdate:
    """Test abulk_update functionality."""

    @pytest.mark.asyncio
    async def test_abulk_update_single_field(self, article_factory):
        """Test abulk_update() with a single field."""
        a1 = await article_factory(title="A1", view_count=1)
        a2 = await article_factory(title="A2", view_count=2)
        a3 = await article_factory(title="A3", view_count=3)

        # Modify in memory
        a1.view_count = 10
        a2.view_count = 20
        a3.view_count = 30

        count = await Article.objects.abulk_update([a1, a2, a3], ["view_count"])

        assert count == 3

        # Verify in database
        articles = await Article.objects.order_by("title").alist()
        assert [a.view_count for a in articles] == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_abulk_update_multiple_fields(self, article_factory):
        """Test abulk_update() with multiple fields."""
        a1 = await article_factory(title="Original 1", view_count=1)
        a2 = await article_factory(title="Original 2", view_count=2)

        a1.title = "Updated 1"
        a1.view_count = 100
        a2.title = "Updated 2"
        a2.view_count = 200

        await Article.objects.abulk_update([a1, a2], ["title", "view_count"])

        articles = await Article.objects.order_by("pk").alist()
        assert articles[0].title == "Updated 1"
        assert articles[0].view_count == 100
        assert articles[1].title == "Updated 2"
        assert articles[1].view_count == 200

    @pytest.mark.asyncio
    async def test_abulk_update_empty_list(self):
        """Test abulk_update() with empty list returns 0."""
        count = await Article.objects.abulk_update([], ["title"])
        assert count == 0


# =============================================================================
# aupdate_or_create Tests
# =============================================================================


class TestUpdateOrCreate:
    """Test aupdate_or_create functionality."""

    @pytest.mark.asyncio
    async def test_aupdate_or_create_creates(self):
        """Test aupdate_or_create() creates when not exists."""
        article, created = await Article.objects.aupdate_or_create(
            title="New Article",
            defaults={"content": "Default content", "view_count": 5},
        )

        assert created is True
        assert article.title == "New Article"
        assert article.content == "Default content"
        assert article.view_count == 5

    @pytest.mark.asyncio
    async def test_aupdate_or_create_updates(self, article_factory):
        """Test aupdate_or_create() updates when exists."""
        existing = await article_factory(title="Existing", view_count=10)

        article, created = await Article.objects.aupdate_or_create(
            title="Existing",
            defaults={"view_count": 999},
        )

        assert created is False
        assert article.pk == existing.pk
        assert article.view_count == 999

    @pytest.mark.asyncio
    async def test_aupdate_or_create_with_create_defaults(self):
        """Test aupdate_or_create() with create_defaults."""
        article, created = await Article.objects.aupdate_or_create(
            title="Create Only",
            defaults={"view_count": 100},
            create_defaults={"content": "Created content"},
        )

        assert created is True
        assert article.content == "Created content"
        assert article.view_count == 100


# =============================================================================
# aaggregate Tests
# =============================================================================


class TestAggregate:
    """Test aaggregate functionality."""

    @pytest.mark.asyncio
    async def test_aaggregate_sum(self, article_factory):
        """Test aaggregate() with Sum."""
        await article_factory(title="A1", view_count=10)
        await article_factory(title="A2", view_count=20)
        await article_factory(title="A3", view_count=30)

        result = await Article.objects.aaggregate(total=Sum("view_count"))

        assert result == {"total": 60}

    @pytest.mark.asyncio
    async def test_aaggregate_with_filter(self, article_factory):
        """Test aaggregate() combined with filter()."""
        await article_factory(title="Published", view_count=100, is_published=True)
        await article_factory(title="Draft", view_count=50, is_published=False)

        result = await Article.objects.filter(is_published=True).aaggregate(total=Sum("view_count"))

        assert result == {"total": 100}

    @pytest.mark.asyncio
    async def test_aaggregate_empty(self):
        """Test aaggregate() on empty queryset."""
        result = await Article.objects.aaggregate(total=Sum("view_count"))

        assert result == {"total": None}


# =============================================================================
# Additional Terminal Method Tests
# =============================================================================


class TestAdditionalTerminalMethods:
    """Test additional async terminal methods."""

    @pytest.mark.asyncio
    async def test_async_iteration_with_select_related(self, author_factory, article_factory):
        """Test async iteration with select_related."""
        author = await author_factory(name="Iterator Author")
        await article_factory(title="Iter Article 1", author_obj=author)
        await article_factory(title="Iter Article 2", author_obj=author)

        results = []
        async for article in Article.objects.select_related("author"):
            results.append(article)

        assert len(results) == 2
        for article in results:
            assert article.author is not None
            assert article.author.name == "Iterator Author"

    @pytest.mark.asyncio
    async def test_afirst_with_select_related(self, author_factory, article_factory):
        """Test afirst() with select_related."""
        author = await author_factory(name="First Author")
        await article_factory(title="First Article", author_obj=author)

        article = await Article.objects.select_related("author").afirst()

        assert article is not None
        assert article.author is not None
        assert article.author.name == "First Author"

    @pytest.mark.asyncio
    async def test_multiple_select_related(self, author_factory, article_factory):
        """Test select_related with multiple different FKs."""
        author1 = await author_factory(name="Author 1")
        author2 = await author_factory(name="Author 2")
        await article_factory(title="Article 1", author_obj=author1)
        await article_factory(title="Article 2", author_obj=author2)
        await article_factory(title="Article 3", author_obj=None)

        articles = await Article.objects.select_related("author").order_by("title").alist()

        assert len(articles) == 3
        assert articles[0].author.name == "Author 1"
        assert articles[1].author.name == "Author 2"
        assert articles[2].author is None


# =============================================================================
# Public API Test
# =============================================================================


class TestPublicAPIExtended:
    """Test extended public API exports."""

    def test_async_model_mixin_import(self):
        """Test AsyncModelMixin can be imported."""
        from turbo_orm import AsyncModelMixin

        assert AsyncModelMixin is not None
