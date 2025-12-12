#!/usr/bin/env python3
"""
Direct SQLite to PostgreSQL Data Migration

Migrates all data directly from SQLite to PostgreSQL using concurrent connections.
Handles binary data (BLOB→BYTEA), preserves foreign key relationships, and validates integrity.

Author: Newsletter Utils Team
Created: 2025-12-01
"""

import sqlite3
import psycopg
from psycopg.rows import dict_row
import os
from pathlib import Path
from dotenv import load_dotenv
import base64


def migrate_table(sqlite_conn, postgres_conn, table_name: str, has_blob: bool = False, has_boolean: bool = False):
    """
    Migrate a single table from SQLite to PostgreSQL.

    Args:
        sqlite_conn: SQLite connection
        postgres_conn: PostgreSQL connection
        table_name: Name of table to migrate
        has_blob: True if table contains BLOB columns (needs special handling)
        has_boolean: True if table contains BOOLEAN columns (convert 0/1 to FALSE/TRUE)
    """
    print(f"\nMigrating table: {table_name}")

    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()

    # Get column info
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    column_info = sqlite_cursor.fetchall()
    columns = [row[1] for row in column_info]

    # For site_cookies: identify boolean columns (secure, http_only)
    boolean_columns = set()
    if has_boolean and table_name == 'site_cookies':
        boolean_columns = {'secure', 'http_only'}  # Column names with boolean type

    # Get row count
    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = sqlite_cursor.fetchone()[0]

    if total_rows == 0:
        print(f"  ✓ {table_name}: 0 rows (empty table, skipped)")
        return 0

    # Fetch all data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    # Build PostgreSQL INSERT statement
    placeholders = ','.join(['%s'] * len(columns))
    columns_str = ','.join(columns)
    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    # Batch insert
    inserted = 0
    batch_size = 1000

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]

        # Process batch: handle BLOB and BOOLEAN conversions
        processed_batch = []
        for row in batch:
            processed_row = list(row)

            # Handle BLOB→BYTEA conversion
            if has_blob:
                # Embedding is column index 1 (url_id, embedding, dimension, created_at)
                if len(processed_row) > 1 and processed_row[1] is not None:
                    # Already bytes in SQLite, psycopg3 handles bytes → BYTEA
                    pass

            # Handle BOOLEAN conversion (0/1 → FALSE/TRUE)
            if has_boolean:
                for idx, col_name in enumerate(columns):
                    if col_name in boolean_columns and processed_row[idx] is not None:
                        # Convert 0→False, 1→True
                        processed_row[idx] = bool(processed_row[idx])

            processed_batch.append(tuple(processed_row))

        # Execute batch
        postgres_cursor.executemany(insert_sql, processed_batch)
        inserted += len(batch)

        if inserted % 5000 == 0:
            print(f"  ... {inserted}/{total_rows} rows")

    postgres_conn.commit()
    print(f"  ✓ {table_name}: {inserted} rows migrated")

    return inserted


def reset_sequences(postgres_conn):
    """
    Reset PostgreSQL sequences after data import.

    This ensures auto-increment IDs continue from the max imported value.
    """
    print("\nResetting PostgreSQL sequences...")

    cursor = postgres_conn.cursor()

    # Get all tables with SERIAL columns
    cursor.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE column_default LIKE 'nextval%'
        AND table_schema = 'public'
    """)

    sequences = cursor.fetchall()

    for table, column in sequences:
        # Set sequence to max value in table
        try:
            cursor.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence(%s, %s),
                    COALESCE((SELECT MAX({column}) FROM "{table}"), 1),
                    true
                )
            """, (table, column))
        except Exception as e:
            print(f"  Warning: Could not reset sequence for {table}.{column}: {e}")

    postgres_conn.commit()
    print(f"  ✓ Reset {len(sequences)} sequences")


def validate_migration(sqlite_conn, postgres_conn):
    """
    Validate that migration was successful by comparing row counts.
    """
    print("\n" + "="*50)
    print("VALIDATION REPORT")
    print("="*50)

    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()

    # Get all table names
    sqlite_cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in sqlite_cursor.fetchall()]

    all_valid = True

    print(f"\n{'Table':<25} {'SQLite':>10} {'PostgreSQL':>12} {'Status':>10}")
    print("-" * 60)

    for table in tables:
        # SQLite count
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        sqlite_count = sqlite_cursor.fetchone()[0]

        # PostgreSQL count
        postgres_cursor.execute(f"SELECT COUNT(*) FROM {table}")
        postgres_count = postgres_cursor.fetchone()[0]

        # Compare
        match = sqlite_count == postgres_count
        status = "✓ PASS" if match else "✗ FAIL"

        print(f"{table:<25} {sqlite_count:>10} {postgres_count:>12} {status:>10}")

        if not match:
            all_valid = False

    print("-" * 60)

    if all_valid:
        print("\n✓ ALL TABLES VALIDATED - Migration successful!")
    else:
        print("\n✗ VALIDATION FAILED - Row count mismatch detected")

    return all_valid


def main():
    """Main migration function"""

    # Load environment variables
    load_dotenv()

    # Paths
    project_root = Path(__file__).parent.parent
    sqlite_db_path = project_root / "data" / "news.db"

    # PostgreSQL connection string
    postgres_url = os.getenv('DATABASE_URL', 'postgresql://newsletter_user:newsletter_pass@localhost:5432/newsletter_db')

    print("="*50)
    print("SQLITE TO POSTGRESQL DATA MIGRATION")
    print("="*50)
    print(f"\nSQLite database: {sqlite_db_path}")
    print(f"PostgreSQL URL: {postgres_url.replace(postgres_url.split('@')[0].split('://')[1], '***')}")

    # Check SQLite database exists
    if not sqlite_db_path.exists():
        print(f"\n✗ ERROR: SQLite database not found: {sqlite_db_path}")
        return 1

    # Connect to databases
    print("\nConnecting to databases...")
    sqlite_conn = sqlite3.connect(str(sqlite_db_path))
    postgres_conn = psycopg.connect(postgres_url, row_factory=dict_row)

    print("✓ Connections established")

    # Define migration order (respect foreign keys)
    # Tables without foreign keys first, then tables that depend on them
    # Format: (table_name, has_blob, has_boolean)
    migration_order = [
        # Core tables (no dependencies)
        ('urls', False, False),

        # Tables that depend on urls
        ('clusters', False, False),
        ('url_embeddings', True, False),  # Has BLOB data!

        # Ranking tables
        ('ranking_runs', False, False),
        ('ranked_urls', False, False),

        # Newsletter tables
        ('newsletters', False, False),
        ('debug_reports', False, False),

        # Pipeline tables
        ('pipeline_executions', False, False),
        ('pipeline_runs', False, False),

        # Other tables
        ('site_cookies', False, True),  # Has BOOLEAN columns!
        ('clustering_runs', False, False),
    ]

    # Migrate each table
    print("\n" + "="*50)
    print("MIGRATING TABLES")
    print("="*50)

    total_migrated = 0

    for table_name, has_blob, has_boolean in migration_order:
        try:
            rows_migrated = migrate_table(sqlite_conn, postgres_conn, table_name, has_blob, has_boolean)
            total_migrated += rows_migrated
        except Exception as e:
            print(f"\n✗ ERROR migrating {table_name}: {e}")
            import traceback
            traceback.print_exc()
            postgres_conn.rollback()
            return 1

    # Reset sequences
    reset_sequences(postgres_conn)

    # Validate migration
    validation_passed = validate_migration(sqlite_conn, postgres_conn)

    # Close connections
    sqlite_conn.close()
    postgres_conn.close()

    print("\n" + "="*50)
    print("MIGRATION SUMMARY")
    print("="*50)
    print(f"Total rows migrated: {total_migrated:,}")
    print(f"Validation: {'PASSED ✓' if validation_passed else 'FAILED ✗'}")

    if validation_passed:
        print("\n✓ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Run integration tests: pytest tests/")
        print("2. Test pipeline: python stages/orchestrator.py --config config/newsletters.yml")
        return 0
    else:
        print("\n✗ Migration validation failed - please review errors above")
        return 1


if __name__ == '__main__':
    exit(main())
