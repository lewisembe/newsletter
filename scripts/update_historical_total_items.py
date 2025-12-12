#!/usr/bin/env python3
"""
Script to update total_items in execution_history with cumulative URL counts.

This recalculates total_items for historical executions based on the sources
they processed, counting total URLs in BD for those sources.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.postgres_db import PostgreSQLURLDatabase


def main():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return 1

    db = PostgreSQLURLDatabase(database_url)

    # Get all executions with parameters
    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get executions that have source_names in parameters
        cursor.execute("""
            SELECT id, parameters, total_items, processed_items, updated_items
            FROM execution_history
            WHERE parameters IS NOT NULL
              AND parameters::jsonb ? 'source_names'
            ORDER BY id
        """)

        executions = cursor.fetchall()

        print(f"Found {len(executions)} executions to update")
        print()

        for execution in executions:
            exec_id = execution['id']
            params = execution['parameters']
            old_total = execution['total_items']
            processed = execution['processed_items']
            updated = execution['updated_items']

            source_names = params.get('source_names', [])

            if not source_names:
                print(f"Execution #{exec_id}: No source_names, skipping")
                continue

            # Calculate new total_items (cumulative count for those sources)
            new_total = db.get_url_count_by_source_names(source_names)

            # Update execution_history
            cursor.execute("""
                UPDATE execution_history
                SET total_items = %s
                WHERE id = %s
            """, (new_total, exec_id))

            print(f"Execution #{exec_id} ({', '.join(source_names)}): {old_total} → {new_total} " +
                  f"(+{processed} new, ~{updated} updated)")

        conn.commit()
        print()
        print(f"✅ Updated {len(executions)} executions")

    return 0


if __name__ == '__main__':
    sys.exit(main())
