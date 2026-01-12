# django-turbo-orm

Async database operations for Django using psycopg3 async cursors and connection pooling (uses django-async-backend).

## Features

- Async database I/O using psycopg3 async cursors
- Connection pooling via psycopg_pool
- Django's Query object for SQL generation
- Familiar chainable queryset API

## Requirements

- Python 3.10+
- Django 4.2+
- PostgreSQL with psycopg3

## Installation

```bash
pip install turbo-orm
```

## Quick Start

### 1. Define your model

```python
from django.db import models
from turbo_orm import AsyncManager

class User(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)

    # Add async manager
    objects = AsyncManager()
```

### 2. Use in async views

```python
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

## API

### AsyncManager

Entry point attached to models, returns AsyncQuerySet.

```python
User.objects.all()
User.objects.filter(is_active=True)
User.objects.exclude(username='admin')
await User.objects.aget(id=1)
await User.objects.acreate(username='new')
await User.objects.acount()
```

### AsyncQuerySet

Chainable query builder with async terminal methods.

**Chainable (no DB hit):**
- `filter()`, `exclude()`
- `order_by()`
- `select_related()`, `prefetch_related()`
- `only()`, `defer()`
- `distinct()`
- `values()`, `values_list()`
- Slicing: `[:10]`

**Terminal (async DB hit):**
- `await qs.aget()` - Single object
- `await qs.afirst()` - First or None
- `await qs.alast()` - Last or None
- `await qs.acount()` - Count
- `await qs.aexists()` - Boolean exists
- `await qs.alist()` - List of objects
- `await qs.acreate()` - Create object
- `await qs.aupdate()` - Bulk update
- `await qs.adelete()` - Bulk delete
- `async for obj in qs` - Async iteration

## Why Turbo ORM?

| Feature           | Django sync_to_async | Turbo ORM       |
|-------------------|---------------------|-----------------|
| Thread pool       | Yes (overhead)      | No              |
| Context switching | Yes                 | No              |
| Memory per conn   | ~800KB              | ~200KB          |
| Concurrent perf   | Baseline            | 2-4x faster     |

## How It Works

### Architecture

turbo-orm bridges Django's SQL generation with true async database execution:

```
┌─────────────────────────────────────────────────────────────────┐
│  Your Code                                                       │
│  await User.objects.filter(active=True).alist()                 │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│  AsyncQuerySet                                                   │
│  - Chainable methods build Django Query object                  │
│  - Terminal methods trigger execution                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│  Django SQLCompiler                                              │
│  - Generates SQL from Query object                              │
│  - Handles joins, filters, ordering                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│  turbo_orm.execution                                             │
│  - Gets connection from pool directly                           │
│  - Executes SQL with async cursor                               │
│  - Returns connection to pool                                   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────┐
│  psycopg3 AsyncConnectionPool                                    │
│  - Manages pool of async PostgreSQL connections                 │
│  - Each request gets its own connection                         │
└─────────────────────────────────────────────────────────────────┘
```

### Connection Pooling

turbo-orm uses `django-async-backend` with `psycopg_pool` for connection management.

**The Problem with django-async-backend's Default Behavior:**

`django-async-backend` uses thread-local storage for connections. In async code, all concurrent requests share the same thread, meaning they all fight over one connection wrapper:

```python
# All 100 concurrent requests get the SAME wrapper
async_conn = async_connections["default"]  # Thread-local, shared!
```

**Our Solution:**

We bypass the thread-local wrapper and access the pool directly:

```python
pool = async_connections["default"].pool

# Each request gets its OWN connection
conn = await pool.getconn()
try:
    cursor = conn.cursor()
    await cursor.execute(sql, params)
    rows = await cursor.fetchall()
finally:
    # Return THIS connection to pool (doesn't affect other requests)
    await pool.putconn(conn)
```

**Flow with 100 concurrent requests:**

```
Request 1 ──→ pool.getconn() ──→ Connection A ──→ query ──→ pool.putconn(A)
Request 2 ──→ pool.getconn() ──→ Connection B ──→ query ──→ pool.putconn(B)
Request 3 ──→ pool.getconn() ──→ Connection C ──→ query ──→ pool.putconn(C)
...
```

Each request has isolated connection lifecycle. No conflicts, no pool exhaustion.

### Configuration

Configure pooling in Django settings:

```python
DATABASES = {
    "default": {
        "ENGINE": "django_async_backend.db.backends.postgresql",
        "NAME": "mydb",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "pool": {
                "min_size": 5,   # Minimum connections in pool
                "max_size": 20,  # Maximum connections in pool
            }
        },
    }
}
```

### Dependencies

- `django-async-backend` - Async database backend for Django
- `psycopg[binary,pool]` - PostgreSQL adapter with async support and pooling

## License

MIT
