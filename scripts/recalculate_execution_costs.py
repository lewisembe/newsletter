#!/usr/bin/env python3
"""
Recalculate execution costs using the new timestamp-based method.

This script fixes the issue where costs were accumulated across multiple
executions on the same day. Now it calculates costs per execution using
the started_at and completed_at timestamps.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.postgres_db import PostgreSQLURLDatabase
from celery_app.utils.cost_calculator import calculate_execution_cost
from dotenv import load_dotenv

# Load environment
load_dotenv()


def main():
    """Recalculate costs for all completed executions."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return 1

    db = PostgreSQLURLDatabase(database_url)

    # Get all completed executions
    executions = db.get_execution_history(limit=1000, status='completed')

    # Filter only those with valid timestamps
    executions = [
        ex for ex in executions
        if ex.get('started_at') and ex.get('completed_at')
    ]

    print(f"Found {len(executions)} completed executions to recalculate")
    print()

    updated_count = 0
    total_old_cost = 0.0
    total_new_cost = 0.0

    for execution in executions:
        exec_id = execution['id']
        stage_name = execution['stage_name']
        old_cost = float(execution['cost_usd']) if execution.get('cost_usd') else 0.0

        # Determine stage number (e.g., "01_extract_urls" -> "01")
        stage_num = stage_name.split('_')[0] if '_' in stage_name else '01'

        # Calculate new cost using timestamp-based method
        cost_data = calculate_execution_cost(exec_id, db=db, stage=stage_num)
        new_cost = cost_data['cost_usd']

        # Update if different
        if abs(old_cost - new_cost) > 0.0001:  # Tolerance for floating point comparison
            db.update_execution_status(
                exec_id,
                'completed',
                input_tokens=cost_data['input_tokens'],
                output_tokens=cost_data['output_tokens'],
                cost_usd=new_cost
            )
            updated_count += 1
            print(f"Execution #{exec_id}: ${old_cost:.4f} → ${new_cost:.4f} (Δ ${new_cost - old_cost:.4f})")

        total_old_cost += old_cost
        total_new_cost += new_cost

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total executions processed: {len(executions)}")
    print(f"Executions updated: {updated_count}")
    print(f"Old total cost: ${total_old_cost:.4f}")
    print(f"New total cost: ${total_new_cost:.4f}")
    print(f"Difference: ${total_new_cost - total_old_cost:.4f}")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
