# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**turbo-orm** is a true async ORM for Django that provides genuine async database operations without thread pool overhead. It bridges Django's Query object (for SQL generation) with django-async-backend (for async cursor execution via psycopg3).

## Commands

```bash
# Install dependencies
just install              # or: uv sync --all-groups

# Run tests (requires PostgreSQL running)
just test                 # or: uv run pytest tests/ -v
just test-file tests/test_async_orm.py  # run a specific test file

# Lint and format
just lint                 # check linting
just lint-fix             # fix linting issues
just fmt                  # format code
just check                # run all checks (fmt-check + lint)

# Database
just db-up                # start PostgreSQL via Docker
just db-down              # stop PostgreSQL

# Build
just build                # build package
```

## Architecture

```
User Code → AsyncManager → AsyncQuerySet → Django SQLCompiler → django-async-backend → PostgreSQL
                                              (SQL generation)    (async cursor)       (psycopg3)
```

### Core Components (`src/turbo_orm/`)

- **manager.py**: `AsyncManager` - Descriptor attached to models, returns `AsyncQuerySet`. Inherits from Django's `BaseManager` for metaclass compatibility.

- **queryset.py**: `AsyncQuerySet` - Chainable query builder wrapping Django's `Query` object. Chainable methods (filter, exclude, order_by) return new querysets without DB hits. Terminal methods (aget, alist, acount) are async and execute queries.

- **execution.py**: SQL execution layer bridging Django's `SQLCompiler` with async cursors. Contains `execute_query`, `execute_insert`, `execute_update`, `execute_delete`, and bulk operations.

- **utils.py**: Row-to-model instance conversion using `Model.from_db()`.

### Key Design Patterns

1. **Chainable methods clone the queryset**: Each filter/exclude/order_by creates a new `AsyncQuerySet` with cloned `Query` object via `_clone()`.

2. **Terminal methods are async**: All database-hitting methods are prefixed with `a` (aget, afirst, alist, acount, acreate, aupdate, adelete).

3. **SQL generation via Django**: Uses `query.get_compiler().as_sql()` to generate SQL, avoiding reimplementation.

4. **Async execution via django-async-backend**: Uses `async_connections[using].cursor()` for true async I/O.

## Testing

Tests require a running PostgreSQL database. Configuration is via environment variables:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=turbo_orm_test
```

The test database engine is `django_async_backend.db.backends.postgresql`. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.

## Dependencies

- Django 4.2+ (tested against 4.2, 5.2, 6.0, and main)
- PostgreSQL with psycopg3
- django-async-backend (provides async database connections)
