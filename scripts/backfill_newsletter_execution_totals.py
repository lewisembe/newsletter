"""
Backfill aggregated token/cost totals for newsletter_executions using their stage records.

Usage:
    PYTHONPATH=. venv/bin/python scripts/backfill_newsletter_execution_totals.py
"""

import os
from dotenv import load_dotenv

from common.postgres_db import PostgreSQLURLDatabase


def main():
    load_dotenv(".env")
    db = PostgreSQLURLDatabase(os.getenv("DATABASE_URL"))

    executions = db.execute_query("SELECT id FROM newsletter_executions ORDER BY id DESC LIMIT 100;")
    updated = 0
    for row in executions:
        exec_id = row["id"]
        stages = db.get_newsletter_stage_executions(exec_id)
        total_input = sum(s.get("input_tokens", 0) or 0 for s in stages)
        total_output = sum(s.get("output_tokens", 0) or 0 for s in stages)
        total_cost = sum(float(s.get("cost_usd") or 0.0) for s in stages)

        status_row = db.execute_query("SELECT status FROM newsletter_executions WHERE id=%s;", (exec_id,), fetch_one=True)
        status = status_row["status"] if status_row else "completed"
        db.update_newsletter_execution_status(
            exec_id,
            status,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=total_cost
        )
        updated += 1

    print(f"[done] updated {updated} newsletter executions")


if __name__ == "__main__":
    main()
