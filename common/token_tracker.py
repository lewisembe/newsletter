"""
Token usage tracker for OpenAI API calls.
Persists token consumption to PostgreSQL (and optionally CSV for fallback).
"""

import csv
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import threading

from .postgres_db import PostgreSQLURLDatabase


class TokenTracker:
    """Track and log OpenAI API token usage to CSV file."""

    def __init__(self, log_file: str = "logs/token_usage.csv", enable_csv: Optional[bool] = None):
        """
        Initialize token tracker.

        Args:
            log_file: Path to CSV log file
        """
        if enable_csv is None:
            # Default: disable CSV unless explicitly enabled via env
            enable_csv = os.getenv("TOKEN_TRACKER_ENABLE_CSV", "false").lower() in ("1", "true", "yes", "on")

        self.enable_csv = enable_csv
        self.log_file = Path(log_file) if enable_csv else None
        self.lock = threading.Lock()  # Thread-safe file writing
        self.db_url = os.getenv("DATABASE_URL")
        self._db = None

        if self.enable_csv and self.log_file:
            # Ensure directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            # Create file with headers if it doesn't exist
            if not self.log_file.exists():
                self._create_csv()

    def _create_csv(self):
        """Create CSV file with headers."""
        if not self.enable_csv or not self.log_file:
            return
        try:
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'date',
                    'stage',
                    'model',
                    'operation',
                    'input_tokens',
                    'output_tokens',
                    'total_tokens',
                    'cost_usd'
                ])
        except Exception:
            pass

    def _get_db(self) -> Optional[PostgreSQLURLDatabase]:
        if not self.db_url:
            return None
        if self._db is None:
            self._db = PostgreSQLURLDatabase(self.db_url)
        return self._db

    def log_usage(
        self,
        stage: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        run_date: Optional[str] = None,
        api_key_id: Optional[int] = None,
        execution_id: Optional[int] = None,
        newsletter_execution_id: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Log token usage to CSV.

        Args:
            stage: Stage number (e.g., "01", "02")
            model: Model name (e.g., "gpt-4o-mini")
            operation: Operation description (e.g., "filter_urls", "classify_article")
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            run_date: Run date in YYYY-MM-DD format (defaults to today)
            api_key_id: Optional API key ID associated to the call
            execution_id: Optional Stage 01 execution ID
            newsletter_execution_id: Optional newsletter execution ID
            timestamp: Override timestamp (defaults to now)
        """
        timestamp = timestamp or datetime.now()
        timestamp_str = timestamp.isoformat()
        date = run_date or datetime.now().strftime('%Y-%m-%d')
        total_tokens = input_tokens + output_tokens
        cost = self._calculate_cost(model, input_tokens, output_tokens)

        # Persist to Postgres
        try:
            db = self._get_db()
            if db:
                db.log_token_usage(
                    timestamp=timestamp,
                    date_value=date,
                    stage=stage,
                    model=model,
                    operation=operation,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    api_key_id=api_key_id,
                    execution_id=execution_id,
                    newsletter_execution_id=newsletter_execution_id
                )
        except Exception:
            # Fallback silently to CSV logging
            pass

        # Optional CSV (only if enabled)
        if self.enable_csv and self.log_file:
            try:
                with self.lock:
                    with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp_str,
                            date,
                            stage,
                            model,
                            operation,
                            input_tokens,
                            output_tokens,
                            total_tokens,
                            f"{cost:.6f}"
                        ])
            except Exception:
                # Swallow CSV errors to not break main flow
                pass

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost in USD based on model pricing.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # OpenAI pricing (as of 2025) - per 1M tokens
        pricing = {
            'gpt-4o': {
                'input': 2.50,   # $2.50 per 1M input tokens
                'output': 10.00  # $10.00 per 1M output tokens
            },
            'gpt-4o-mini': {
                'input': 0.150,  # $0.15 per 1M input tokens
                'output': 0.600  # $0.60 per 1M output tokens
            },
            'gpt-4-turbo': {
                'input': 10.00,
                'output': 30.00
            },
            'gpt-3.5-turbo': {
                'input': 0.50,
                'output': 1.50
            }
        }

        # Get pricing for model (default to gpt-4o-mini if unknown)
        model_pricing = pricing.get(model, pricing['gpt-4o-mini'])

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * model_pricing['input']
        output_cost = (output_tokens / 1_000_000) * model_pricing['output']

        return input_cost + output_cost

    def get_summary(
        self,
        date: Optional[str] = None,
        stage: Optional[str] = None
    ) -> dict:
        """
        Get summary statistics for token usage.

        Args:
            date: Filter by date (YYYY-MM-DD)
            stage: Filter by stage number

        Returns:
            Dictionary with summary statistics
        """
        if not self.log_file.exists():
            return {
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'calls': 0
            }

        total_input = 0
        total_output = 0
        total_cost = 0.0
        calls = 0

        with open(self.log_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Apply filters
                if date and row['date'] != date:
                    continue
                if stage and row['stage'] != stage:
                    continue

                total_input += int(row['input_tokens'])
                total_output += int(row['output_tokens'])
                total_cost += float(row['cost_usd'])
                calls += 1

        return {
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_input + total_output,
            'total_cost': total_cost,
            'calls': calls
        }


# Global singleton instance
_tracker = None


def get_tracker() -> TokenTracker:
    """
    Get global TokenTracker instance.

    Returns:
        TokenTracker singleton instance
    """
    global _tracker
    if _tracker is None:
        _tracker = TokenTracker()
    return _tracker


def log_tokens(
    stage: str,
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    run_date: Optional[str] = None,
    api_key_id: Optional[int] = None,
    execution_id: Optional[int] = None,
    newsletter_execution_id: Optional[int] = None,
    timestamp: Optional[datetime] = None
):
    """
    Convenience function to log token usage.

    Args:
        stage: Stage number (e.g., "01", "02")
        model: Model name
        operation: Operation description
        input_tokens: Input tokens used
        output_tokens: Output tokens used
        run_date: Run date (optional)
        api_key_id: API key ID used for this call (optional)
        execution_id: Stage 01 execution ID (optional)
        newsletter_execution_id: Newsletter execution ID (optional)
        timestamp: Optional datetime for the log
    """
    # Allow passing context via environment variables if not provided
    if execution_id is None:
        env_exec = os.getenv("TOKEN_TRACKER_EXECUTION_ID")
        if env_exec and env_exec.isdigit():
            execution_id = int(env_exec)
    if newsletter_execution_id is None:
        env_news = os.getenv("TOKEN_TRACKER_NEWSLETTER_EXECUTION_ID")
        if env_news and env_news.isdigit():
            newsletter_execution_id = int(env_news)

    tracker = get_tracker()
    tracker.log_usage(
        stage=stage,
        model=model,
        operation=operation,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        run_date=run_date,
        api_key_id=api_key_id,
        execution_id=execution_id,
        newsletter_execution_id=newsletter_execution_id,
        timestamp=timestamp
    )

    # Note: api_key_id is currently not logged to CSV but is tracked via database
    # update_api_key_usage() call in LLMClient.call()
