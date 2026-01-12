# Sample Project

Django project demonstrating django-pg-textsearch with BM25 full-text search.

## Quick Start

```bash
# Install dependencies
uv sync

# Start PostgreSQL with pg_textsearch
just up

# Run migrations and seed data
just migrate
just seed

# Or do it all at once
just setup
```

## Usage

```bash
# Search for articles
just search "postgresql"
just search "web framework"
just search "machine learning"

# Search with limit
just search-limit "database" 3

# Search with threshold filter (only matching documents)
just search-filter "postgresql" -1.0
```

## Commands

| Command | Description |
|---------|-------------|
| `just up` | Start PostgreSQL with pg_textsearch |
| `just down` | Stop PostgreSQL |
| `just migrate` | Run Django migrations |
| `just seed` | Seed sample articles |
| `just search "query"` | Search articles |
| `just setup` | Full setup (up + migrate + seed) |
| `just reset` | Reset everything and start fresh |
