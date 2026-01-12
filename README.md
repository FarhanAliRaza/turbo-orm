# turbo-orm

True async ORM for Django - genuine async database operations without thread pool overhead.

## Features

- **True Async** - No `sync_to_async` wrappers, real async database I/O
- **Django Compatible** - Uses Django's Query object for SQL generation
- **Familiar API** - Same chainable queryset interface you know
- **High Performance** - 2-4x throughput improvement under concurrent load

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

## License

MIT
