# django-turbo-orm

> **Experimental** - This library is under active development. API may change.

Async database operations for Django using psycopg3 async cursors and connection pooling.

Built on top of [django-async-backend](https://github.com/Arfey/django-async-backend) for async database connections.

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
pip install django-turbo-orm
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

    # Terminal (async DB hit)
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

| Feature           | Django sync_to_async | Turbo ORM   |
| ----------------- | -------------------- | ----------- |
| Thread pool       | Yes (overhead)       | No          |
| Context switching | Yes                  | No          |
| Memory per conn   | ~800KB               | ~200KB      |
| Concurrent perf   | Baseline             | 2-4x faster |

## How It Works

### Architecture

turbo-orm bridges Django's SQL generation with async database execution:

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
        "OPTIONS": {
            "pool": {
                "min_size": 5,   # Minimum connections in pool
                "max_size": 20,  # Maximum connections in pool
            }
        },
    }
}
```

**Default Pool (auto-created if not configured):**

If you don't configure a pool, turbo-orm automatically creates one with:

- `min_size`: 2
- `max_size`: 10

For production, configure explicit pool sizes based on your workload.

### Dependencies

- `django-async-backend` - Async database backend for Django
- `psycopg[binary,pool]` - PostgreSQL adapter with async support and pooling

## License

MIT
