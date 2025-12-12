"""
Backfill token_usage data into Postgres from logs/token_usage.csv

Usage:
    python scripts/backfill_token_usage.py [--csv path] [--force]

Notes:
- Requires DATABASE_URL env var.
- Skips import if the token_usage table already has rows unless --force.
"""

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from common.postgres_db import PostgreSQLURLDatabase


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill token_usage into Postgres")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("logs") / "token_usage.csv",
        help="Path to token_usage CSV (default: logs/token_usage.csv)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Import even if token_usage table already has data (will truncate table first)",
    )
    return parser.parse_args()


def ensure_db():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL env var is required")
    return PostgreSQLURLDatabase(db_url)


def table_has_rows(db: PostgreSQLURLDatabase) -> bool:
    db._ensure_token_usage_table()
    row = db.execute_query("SELECT COUNT(*) AS c FROM token_usage;", fetch_one=True)
    return bool(row and row.get("c", 0) > 0)


def truncate_table(db: PostgreSQLURLDatabase):
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE token_usage;")
        conn.commit()


def main():
    args = parse_args()
    csv_path = args.csv

    if not csv_path.exists():
        print(f"[skip] CSV not found: {csv_path}")
        return

    db = ensure_db()

    if table_has_rows(db):
        if not args.force:
            print("[skip] token_usage already has data. Use --force to import anyway.")
            return
        truncate_table(db)
        print("[info] token_usage truncated (force import).")

    imported = 0
    default_fields = [
        "timestamp",
        "date",
        "stage",
        "model",
        "operation",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
    ]

    with csv_path.open() as f:
        reader = csv.DictReader(f)

        # If the CSV has no headers, re-read using default headers
        if not reader.fieldnames or "timestamp" not in reader.fieldnames:
            f.seek(0)
            reader = csv.DictReader(f, fieldnames=default_fields)

        for row in reader:
            try:
                ts = row.get("timestamp")
                if not ts or ts.lower() == "timestamp":
                    continue
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)

                date_raw = row.get("date")
                try:
                    if date_raw and date_raw.lower() != "date":
                        date_value = datetime.fromisoformat(str(date_raw)).date() if "T" in date_raw else datetime.strptime(str(date_raw), "%Y-%m-%d").date()
                    else:
                        date_value = ts_dt.date()
                except Exception:
                    print(f"[warn] Skipping row with invalid date: {date_raw}")
                    continue

                db.log_token_usage(
                    timestamp=ts_dt,
                    date_value=date_value,
                    stage=row.get("stage"),
                    model=row.get("model"),
                    operation=row.get("operation"),
                    input_tokens=int(row.get("input_tokens") or 0),
                    output_tokens=int(row.get("output_tokens") or 0),
                    cost_usd=float(row.get("cost_usd") or 0.0),
                    api_key_id=None,
                    execution_id=None,
                    newsletter_execution_id=None,
                )
                imported += 1
            except Exception as e:
                print(f"[warn] Skipping row due to error: {e}")

    print(f"[done] Imported {imported} rows from {csv_path}")


if __name__ == "__main__":
    main()
