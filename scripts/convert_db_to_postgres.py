#!/usr/bin/env python3
"""
Automated conversion of SQLiteURLDatabase to PostgreSQLURLDatabase

Converts db.py from sqlite3 to psycopg3 with minimal manual intervention.
"""

import re
from pathlib import Path


def convert_sqlite_to_postgres(sqlite_file: str, postgres_file: str):
    """Convert SQLite database class to PostgreSQL"""

    with open(sqlite_file, 'r') as f:
        content = f.read()

    # Step 1: Update imports
    content = re.sub(
        r'import sqlite3',
        'import psycopg\nfrom psycopg.rows import dict_row\nfrom psycopg_pool import ConnectionPool',
        content
    )

    # Step 2: Update class name
    content = re.sub(
        r'class SQLiteURLDatabase:',
        'class PostgreSQLURLDatabase:',
        content
    )

    # Step 3: Update docstring
    content = re.sub(
        r'SQLite database manager',
        'PostgreSQL database manager',
        content
    )
    content = re.sub(
        r'SQLite',
        'PostgreSQL',
        content,
        count=10  # Only first few occurrences in docstrings
    )

    # Step 4: Update constructor parameter
    content = re.sub(
        r'def __init__\(self, db_path: str = "data/news\.db"\):',
        'def __init__(self, connection_string: str):',
        content
    )
    content = re.sub(
        r'self\.db_path = db_path',
        'self.connection_string = connection_string',
        content
    )

    # Step 5: Remove _ensure_directory method (not needed for PostgreSQL)
    content = re.sub(
        r'    def _ensure_directory\(self\):.*?logger\.info\(f"Created database directory: \{db_dir\}"\)\n',
        '',
        content,
        flags=re.DOTALL
    )

    # Step 6: Update get_connection method for PostgreSQL
    old_connection = r'''    @contextmanager
    def get_connection\(self\):
        """
        Context manager for database connections\.

        Ensures proper connection cleanup and error handling\.

        Usage:
            with db\.get_connection\(\) as conn:
                cursor = conn\.cursor\(\)
                cursor\.execute\("SELECT \.\.\."\)
        """
        conn = None
        try:
            conn = sqlite3\.connect\(self\.db_path\)
            conn\.row_factory = sqlite3\.Row  # Enable column access by name
            conn\.execute\("PRAGMA foreign_keys = ON"\)
            yield conn
        except sqlite3\.Error as e:
            logger\.error\(f"Database connection error: \{e\}"\)
            if conn:
                conn\.rollback\(\)
            raise
        finally:
            if conn:
                conn\.close\(\)'''

    new_connection = '''    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Ensures proper connection cleanup and error handling.

        Usage:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        conn = None
        try:
            conn = psycopg.connect(self.connection_string, row_factory=dict_row)
            conn.autocommit = False
            yield conn
        except psycopg.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()'''

    content = re.sub(old_connection, new_connection, content, flags=re.DOTALL)

    # Step 7: Replace placeholders ? → %s
    # This is the most critical change for query compatibility
    content = re.sub(r'("\s*)(\?)', r'\1%s', content)  # In strings starting with "
    content = re.sub(r"('\s*)(\?)", r'\1%s', content)  # In strings starting with '

    # Step 8: Remove PRAGMA statements
    content = re.sub(r'\s*conn\.execute\("PRAGMA.*?"\)\n', '', content)
    content = re.sub(r'\s*cursor\.execute\("PRAGMA.*?"\).*?\n', '', content)

    # Step 9: Handle sqlite3.Binary → bytes (psycopg3 handles automatically)
    content = re.sub(r'sqlite3\.Binary\(([^)]+)\)', r'\1', content)

    # Step 10: Update exception handling
    content = re.sub(r'sqlite3\.IntegrityError', 'psycopg.errors.UniqueViolation', content)
    content = re.sub(r'sqlite3\.Error', 'psycopg.Error', content)

    # Step 11: Skip init_db (schema already created)
    content = re.sub(
        r'    def init_db\(self.*?logger\.info\("Database schema initialized.*?\n',
        '    def init_db(self, drop_existing: bool = False):\n        """\n        Schema initialization skipped - use PostgreSQL schema file instead.\n        """\n        logger.info("PostgreSQL schema managed externally (docker/schemas/schema_manual.sql)")\n        pass\n',
        content,
        flags=re.DOTALL
    )

    # Write to output file
    with open(postgres_file, 'w') as f:
        f.write(content)

    print(f"✓ Converted {sqlite_file} → {postgres_file}")
    print(f"  Lines: {len(content.splitlines())}")


if __name__ == '__main__':
    project_root = Path(__file__).parent.parent
    sqlite_file = project_root / "common" / "db.py"
    postgres_file = project_root / "common" / "postgres_db.py"

    convert_sqlite_to_postgres(str(sqlite_file), str(postgres_file))
