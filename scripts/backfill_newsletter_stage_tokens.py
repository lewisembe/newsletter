"""
Backfill token/cost metrics for newsletter stage executions using token_usage and timestamps.

Usage:
    PYTHONPATH=. venv/bin/python scripts/backfill_newsletter_stage_tokens.py
"""

import os
from datetime import datetime
from dotenv import load_dotenv

from common.postgres_db import PostgreSQLURLDatabase


def main():
    load_dotenv(".env")
    db = PostgreSQLURLDatabase(os.getenv("DATABASE_URL"))

    executions = db.execute_query("""
        SELECT id FROM newsletter_executions
        ORDER BY created_at DESC
        LIMIT 50;
    """)

    updated = 0
    for row in executions:
        exec_id = row["id"]
        stages = db.get_newsletter_stage_executions(exec_id)
        for stage in stages:
            start = stage.get("started_at")
            end = stage.get("completed_at") or datetime.utcnow()
            if not start:
                continue

            usage = db.get_token_usage_between(
                stage=str(stage.get("stage_number")).zfill(2),
                start_ts=start,
                end_ts=end
            )
            costs = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cost_usd": float(usage.get("cost_usd", 0.0)),
            }

            db.update_newsletter_stage_execution_status(
                stage["id"],
                stage.get("status", "completed"),
                input_tokens=costs["input_tokens"],
                output_tokens=costs["output_tokens"],
                cost_usd=costs["cost_usd"]
            )
            updated += 1

    print(f"[done] updated {updated} stage rows")


if __name__ == "__main__":
    main()
