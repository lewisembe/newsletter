#!/usr/bin/env python3
"""
SQLite to PostgreSQL Schema Migration Script

Converts SQLite database schema to PostgreSQL-compatible SQL.
Handles data types, constraints, indexes, triggers, and views.

Author: Newsletter Utils Team
Created: 2025-12-01
"""

import sqlite3
import re
import os
from pathlib import Path


def convert_sqlite_to_postgres_type(sqlite_type: str) -> str:
    """Convert SQLite data type to PostgreSQL equivalent"""
    type_map = {
        'INTEGER': 'INTEGER',
        'TEXT': 'TEXT',
        'REAL': 'DOUBLE PRECISION',
        'BLOB': 'BYTEA',
        'BOOLEAN': 'BOOLEAN',
        'TIMESTAMP': 'TIMESTAMP WITH TIME ZONE',
    }

    # Handle INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
    if 'INTEGER PRIMARY KEY AUTOINCREMENT' in sqlite_type.upper():
        return 'SERIAL PRIMARY KEY'

    for sqlite, postgres in type_map.items():
        if sqlite in sqlite_type.upper():
            return postgres

    return sqlite_type


def convert_table_ddl(sqlite_ddl: str) -> str:
    """Convert CREATE TABLE statement from SQLite to PostgreSQL"""

    # Replace INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
    ddl = re.sub(
        r'(\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
        r'\1 SERIAL PRIMARY KEY',
        sqlite_ddl,
        flags=re.IGNORECASE
    )

    # Replace BLOB → BYTEA
    ddl = re.sub(r'\bBLOB\b', 'BYTEA', ddl, flags=re.IGNORECASE)

    # Replace TIMESTAMP → TIMESTAMP WITH TIME ZONE
    ddl = re.sub(r'\bTIMESTAMP\b', 'TIMESTAMP WITH TIME ZONE', ddl)

    # Remove AUTOINCREMENT keyword (not needed after SERIAL conversion)
    ddl = re.sub(r'\s+AUTOINCREMENT\b', '', ddl, flags=re.IGNORECASE)

    # Keep CHECK constraints as-is (compatible)
    # Keep FOREIGN KEY constraints as-is (compatible)
    # Keep UNIQUE constraints as-is (compatible)

    return ddl


def generate_postgres_triggers() -> str:
    """Generate PostgreSQL trigger functions and triggers"""

    triggers = """
-- PostgreSQL Trigger Functions
-- These replace SQLite's AFTER UPDATE triggers for auto-updating timestamps

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply timestamp trigger to tables with updated_at column
CREATE TRIGGER update_urls_timestamp
    BEFORE UPDATE ON urls
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_clusters_timestamp
    BEFORE UPDATE ON clusters
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER update_site_cookies_timestamp
    BEFORE UPDATE ON site_cookies
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();
"""

    return triggers


def generate_postgres_view() -> str:
    """Generate PostgreSQL view definition"""

    view = """
-- URLs with Cluster Information (read-only view)
CREATE OR REPLACE VIEW urls_with_cluster AS
SELECT
    u.id,
    u.url,
    u.title,
    u.source,
    u.content_type,
    u.content_subtype,
    u.categoria_tematica,
    u.extracted_at,
    u.last_extracted_at,
    u.cluster_id,
    u.cluster_assigned_at,
    c.cluster_name,
    c.article_count as cluster_size,
    c.avg_similarity as cluster_similarity
FROM urls u
LEFT JOIN clusters c ON u.cluster_id = c.id;
"""

    return view


def migrate_schema(sqlite_db_path: str, output_file: str):
    """
    Main migration function.

    Reads SQLite schema, converts to PostgreSQL, outputs to SQL file.
    """

    print(f"Migrating schema from: {sqlite_db_path}")
    print(f"Output file: {output_file}")

    # Connect to SQLite database
    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()

    # Get all table schemas (exclude internal sqlite tables)
    cursor.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = cursor.fetchall()

    # Get all index schemas
    cursor.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='index'
        AND name NOT LIKE 'sqlite_%'
        AND sql IS NOT NULL
        ORDER BY name
    """)
    indexes = cursor.fetchall()

    # Get view schemas
    cursor.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='view'
        ORDER BY name
    """)
    views = cursor.fetchall()

    conn.close()

    # Start writing PostgreSQL schema
    with open(output_file, 'w') as f:
        f.write("-- PostgreSQL Schema Migration\n")
        f.write("-- Migrated from SQLite database: data/news.db\n")
        f.write(f"-- Generated: {output_file}\n")
        f.write("-- \n")
        f.write("-- This schema creates all tables, indexes, triggers, and views\n")
        f.write("-- for the newsletter pipeline application.\n")
        f.write("--\n\n")

        f.write("-- Enable required PostgreSQL extensions\n")
        f.write("CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text similarity\n\n")

        f.write("-- ============================================\n")
        f.write("-- TABLES\n")
        f.write("-- ============================================\n\n")

        # Convert and write tables
        for table_name, sqlite_ddl in tables:
            if sqlite_ddl:
                # Convert table DDL
                postgres_ddl = convert_table_ddl(sqlite_ddl)

                f.write(f"-- Table: {table_name}\n")
                f.write(postgres_ddl + ";\n\n")

        f.write("\n-- ============================================\n")
        f.write("-- INDEXES\n")
        f.write("-- ============================================\n\n")

        # Write indexes (mostly compatible, just need minor cleanup)
        for index_name, sqlite_ddl in indexes:
            if sqlite_ddl:
                # Remove IF NOT EXISTS (optional, for cleaner output)
                postgres_ddl = sqlite_ddl.replace('IF NOT EXISTS', '')

                f.write(f"-- Index: {index_name}\n")
                f.write(postgres_ddl + ";\n\n")

        f.write("\n-- ============================================\n")
        f.write("-- TRIGGERS\n")
        f.write("-- ============================================\n\n")

        # Write trigger functions
        f.write(generate_postgres_triggers())

        f.write("\n-- ============================================\n")
        f.write("-- VIEWS\n")
        f.write("-- ============================================\n\n")

        # Write views
        f.write(generate_postgres_view())

        f.write("\n-- ============================================\n")
        f.write("-- MIGRATION COMPLETE\n")
        f.write("-- ============================================\n")
        f.write("-- \n")
        f.write("-- To apply this schema to PostgreSQL:\n")
        f.write("-- docker-compose exec -T postgres psql -U newsletter_user newsletter_db < docker/schemas/schema.sql\n")
        f.write("--\n")

    # Print summary
    print(f"\n✓ Schema migration complete!")
    print(f"  Tables:  {len(tables)}")
    print(f"  Indexes: {len(indexes)}")
    print(f"  Triggers: 3 (timestamp auto-update)")
    print(f"  Views:   1 (urls_with_cluster)")
    print(f"\nOutput: {output_file}")
    print(f"\nNext steps:")
    print(f"1. Review the generated schema file")
    print(f"2. Apply to PostgreSQL: docker-compose exec -T postgres psql -U newsletter_user newsletter_db < {output_file}")
    print(f"3. Verify tables created: docker-compose exec postgres psql -U newsletter_user newsletter_db -c '\\dt'")


def main():
    """Entry point"""

    # Paths
    project_root = Path(__file__).parent.parent
    sqlite_db_path = project_root / "data" / "news.db"
    output_dir = project_root / "docker" / "schemas"
    output_file = output_dir / "schema.sql"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if SQLite database exists
    if not sqlite_db_path.exists():
        print(f"ERROR: SQLite database not found: {sqlite_db_path}")
        print("Please ensure data/news.db exists before running migration.")
        return 1

    # Run migration
    try:
        migrate_schema(str(sqlite_db_path), str(output_file))
        return 0
    except Exception as e:
        print(f"\n ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
