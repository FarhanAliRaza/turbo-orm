# Turbo ORM Library Plan

## Overview

Build a library that bridges **django-async-backend** (true async cursors) with **Django's ORM** (SQL generation), creating a true async ORM without thread pool overhead.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User Code                                                          │
│       │                                                              │
│       ▼                                                              │
│   AsyncManager.filter().order_by()[:10]   (Chainable, Lazy)         │
│       │                                                              │
│       ▼                                                              │
│   AsyncQuerySet.aget() / .acount() / async for  (Terminal Methods)  │
│       │                                                              │
│       ├──────────────────────────────────────┐                      │
│       ▼                                      ▼                      │
│   Django's SQLCompiler              django-async-backend            │
│   (Generates SQL)                   (Async Cursor Execution)        │
│       │                                      │                      │
│       └──────────────────────────────────────┘                      │
│                       │                                              │
│                       ▼                                              │
│               PostgreSQL (psycopg3 async)                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Components to Build

### 1. AsyncQuerySet

**Purpose**: Chainable query builder that stays lazy until terminal method is called.

**Key Insight**: Reuse Django's `Query` object for all query building, only replace execution.

```python
class AsyncQuerySet:
    def __init__(self, model, query=None, using='default'):
        self.model = model
        self.query = query or Query(model)  # Django's Query object
        self._db = using

    # Chainable methods (return new AsyncQuerySet, no DB hit)
    def filter(self, *args, **kwargs) -> 'AsyncQuerySet'
    def exclude(self, *args, **kwargs) -> 'AsyncQuerySet'
    def order_by(self, *fields) -> 'AsyncQuerySet'
    def select_related(self, *fields) -> 'AsyncQuerySet'
    def prefetch_related(self, *lookups) -> 'AsyncQuerySet'
    def only(self, *fields) -> 'AsyncQuerySet'
    def defer(self, *fields) -> 'AsyncQuerySet'
    def distinct(self) -> 'AsyncQuerySet'
    def values(self, *fields) -> 'AsyncQuerySet'
    def values_list(self, *fields, flat=False) -> 'AsyncQuerySet'
    def __getitem__(self, k) -> 'AsyncQuerySet'  # Slicing

    # Terminal async methods (hit DB with true async)
    async def aget(self, *args, **kwargs) -> Model
    async def afirst(self) -> Optional[Model]
    async def alast(self) -> Optional[Model]
    async def acount(self) -> int
    async def aexists(self) -> bool
    async def acreate(self, **kwargs) -> Model
    async def aupdate(self, **kwargs) -> int
    async def adelete(self) -> tuple[int, dict]
    async def abulk_create(self, objs) -> list[Model]
    async def abulk_update(self, objs, fields) -> int
    async def aget_or_create(self, **kwargs) -> tuple[Model, bool]
    async def aupdate_or_create(self, **kwargs) -> tuple[Model, bool]
    async def ain_bulk(self, id_list) -> dict
    async def alist(self) -> list[Model]  # Convenience method

    # Async iteration
    async def __aiter__(self) -> AsyncIterator[Model]
```

### 2. AsyncManager

**Purpose**: Entry point attached to models, returns AsyncQuerySet.

```python
class AsyncManager:
    def __init__(self):
        self.model = None
        self._db = 'default'

    def __get__(self, obj, objtype=None):
        # Descriptor protocol for model attachment
        ...

    def get_queryset(self) -> AsyncQuerySet:
        return AsyncQuerySet(self.model, using=self._db)

    def all(self) -> AsyncQuerySet
    def filter(self, *args, **kwargs) -> AsyncQuerySet
    def exclude(self, *args, **kwargs) -> AsyncQuerySet

    # Async shortcuts
    async def aget(self, *args, **kwargs) -> Model
    async def acreate(self, **kwargs) -> Model
    async def acount(self) -> int
```

### 3. SQL Execution Layer

**Purpose**: Bridge between Django's compiled SQL and async cursors.

```python
async def execute_sql(query, using='default'):
    """Execute compiled SQL using async cursor."""
    from django_async_backend.db import async_connections

    compiler = query.get_compiler(using=using)
    sql, params = compiler.as_sql()

    async with async_connections[using].cursor() as cursor:
        await cursor.execute(sql, params)
        return cursor

async def fetch_all(cursor) -> list[tuple]:
    return await cursor.fetchall()

async def fetch_one(cursor) -> Optional[tuple]:
    return await cursor.fetchone()

async def fetch_many(cursor, size=100) -> list[tuple]:
    return await cursor.fetchmany(size)
```

### 4. Model Instance Factory

**Purpose**: Convert database rows back to model instances.

```python
def row_to_instance(model, row, fields):
    """Convert a database row to a model instance."""
    instance = model()
    for field, value in zip(fields, row):
        setattr(instance, field.attname, value)
    instance._state.adding = False
    instance._state.db = using
    return instance

def get_concrete_fields(model):
    """Get fields that map to database columns."""
    return model._meta.concrete_fields
```

---

## File Structure

```
turbo_orm/
├── __init__.py           # Public API exports
├── manager.py            # AsyncManager class
├── queryset.py           # AsyncQuerySet class
├── execution.py          # SQL execution with async cursors
├── compiler.py           # Extensions to Django's compiler (if needed)
├── exceptions.py         # Custom exceptions
└── utils.py              # Helper functions (row_to_instance, etc.)
```

---

## Implementation Steps

### Phase 1: Core Foundation

- [ ] Create `AsyncQuerySet` with `__init__` and `_clone()`
- [ ] Implement chainable methods that modify `self.query`
- [ ] Create `AsyncManager` descriptor

### Phase 2: Read Operations

- [ ] Implement `_compile()` to get SQL from Django's compiler
- [ ] Implement `_execute()` to run SQL with async cursor
- [ ] Implement `_row_to_instance()` for model hydration
- [ ] Implement `aget()`, `afirst()`, `alast()`
- [ ] Implement `acount()`, `aexists()`
- [ ] Implement `async __aiter__()` with chunked fetching
- [ ] Implement `alist()` convenience method

### Phase 3: Write Operations

- [ ] Implement `acreate()` with RETURNING clause
- [ ] Implement `aupdate()` for bulk updates
- [ ] Implement `adelete()` for bulk deletes
- [ ] Implement `abulk_create()`
- [ ] Implement `aget_or_create()`, `aupdate_or_create()`

### Phase 4: Advanced Features

- [ ] Implement `values()` and `values_list()` return types
- [ ] Implement `select_related()` with JOIN handling
- [ ] Implement `prefetch_related()` with async prefetching
- [ ] Implement `annotate()` and `aggregate()`
- [ ] Transaction support with `async_atomic`

### Phase 5: Integration & Testing

- [ ] Create benchmark endpoints
- [ ] Compare performance vs Django's sync_to_async ORM
- [ ] Compare performance vs raw SQL
- [ ] Document API

---

## Key Technical Details

### Reusing Django's Query Building

```python
def filter(self, *args, **kwargs):
    clone = self._clone()
    # Use Django's Q objects and query internals
    clone.query.add_q(Q(*args, **kwargs))
    return clone

def order_by(self, *fields):
    clone = self._clone()
    clone.query.clear_ordering(force=True)
    clone.query.add_ordering(*fields)
    return clone

def __getitem__(self, k):
    clone = self._clone()
    if isinstance(k, slice):
        clone.query.set_limits(k.start, k.stop)
    return clone
```

### SQL Compilation (Reuse Django's Compiler)

```python
def _compile(self):
    """Use Django's SQL compiler - this is the key reuse!"""
    from django.db import connections
    connection = connections[self._db]
    compiler = self.query.get_compiler(using=self._db, connection=connection)
    return compiler.as_sql()  # Returns (sql, params)
```

### Async Execution (Use django-async-backend)

```python
async def _execute(self, sql, params):
    """Execute with true async cursor."""
    from django_async_backend.db import async_connections

    async with async_connections[self._db].cursor() as cursor:
        await cursor.execute(sql, params)
        return await cursor.fetchall()
```

### Model Hydration

```python
def _rows_to_instances(self, rows):
    """Convert rows to model instances."""
    opts = self.model._meta
    fields = opts.concrete_fields
    field_names = [f.attname for f in fields]

    instances = []
    for row in rows:
        instance = self.model(**dict(zip(field_names, row)))
        instance._state.adding = False
        instance._state.db = self._db
        instances.append(instance)
    return instances
```

---

## Usage Example (After Implementation)

```python
# models.py
from django.db import models
from turbo_orm import AsyncManager

class User(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)

    # Add async manager
    objects = AsyncManager()

# views.py
async def get_users(request):
    # Chainable (lazy, no DB hit)
    qs = User.objects.filter(is_active=True).order_by('-id')[:10]

    # Terminal (true async DB hit)
    users = await qs.alist()

    # Or iterate
    async for user in qs:
        print(user.username)

    # Single object
    user = await User.objects.aget(id=1)

    # Count
    count = await User.objects.filter(is_active=True).acount()

    # Create
    new_user = await User.objects.acreate(
        username='test',
        email='test@example.com'
    )
```

---

## Requirements

- Python 3.12+
- Django 5.0+
- PostgreSQL (required by django-async-backend)
- psycopg[binary] >= 3.0
- django-async-backend

```toml
# pyproject.toml
[project]
dependencies = [
    "django>=5.0",
    "psycopg[binary]>=3.0",
    "django-async-backend",
]
```

---

## Expected Performance Gains

| Scenario                  | Django (sync_to_async) | True Async ORM | Improvement |
| ------------------------- | ---------------------- | -------------- | ----------- |
| 100 concurrent requests   | ~2,000 req/s           | ~5,000 req/s   | 2.5x        |
| 1000 concurrent requests  | ~1,500 req/s           | ~6,000 req/s   | 4x          |
| Memory (1000 connections) | ~800MB                 | ~200MB         | 75% less    |
| P99 Latency               | ~50ms                  | ~15ms          | 70% lower   |

The gains come from:

1. No thread pool overhead
2. No context switching between threads
3. Native async I/O multiplexing
4. Lower memory per connection

---

## Risks & Mitigations

| Risk                                | Mitigation                                |
| ----------------------------------- | ----------------------------------------- |
| Django's Query internals change     | Pin Django version, add tests             |
| Complex queries (JOINs, subqueries) | Start simple, add incrementally           |
| Transaction handling                | Use django-async-backend's `async_atomic` |
| Connection pooling                  | Leverage psycopg's async pool             |

---

## Next Steps

1. **Setup PostgreSQL** for benchmark project
2. **Install django-async-backend**
3. **Create the library** in `/home/farhan/code/benchmark/turbo_orm/`
4. **Implement Phase 1-2** (enough for benchmarking reads)
5. **Run benchmarks** comparing all approaches
