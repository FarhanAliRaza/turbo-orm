#!/usr/bin/env python
"""Setup test database for turbo-orm tests."""

import os
import sys

import psycopg

DB_NAME = os.environ.get("POSTGRES_DB", "turbo_orm_test")
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
DB_HOST = os.environ.get("POSTGRES_HOST", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5432")


def main():
    # Connect to postgres database to create test database
    conn = psycopg.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        autocommit=True,
    )

    with conn.cursor() as cur:
        # Drop if exists
        cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        print(f"Dropped database {DB_NAME} (if existed)")

        # Create database
        cur.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"Created database {DB_NAME}")

    conn.close()

    # Now connect to the test database and create tables
    conn = psycopg.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        autocommit=True,
    )

    with conn.cursor() as cur:
        # Create Article table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tests_article (
                id BIGSERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                author VARCHAR(100) DEFAULT '',
                published_at TIMESTAMPTZ DEFAULT NOW(),
                is_published BOOLEAN DEFAULT FALSE,
                view_count INTEGER DEFAULT 0
            )
        """)
        print("Created tests_article table")

        # Create Category table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tests_category (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT DEFAULT ''
            )
        """)
        print("Created tests_category table")

    conn.close()
    print("Database setup complete!")


if __name__ == "__main__":
    main()
