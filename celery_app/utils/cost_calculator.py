"""
Cost calculator for executions using token_usage stored in Postgres.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_execution_cost(execution_id: int, db=None, stage: str = '01'):
    """
    Calculate costs from logs/token_usage.csv for a specific execution.

    Uses execution's started_at and completed_at timestamps to filter
    only the tokens consumed during that execution.

    Args:
        execution_id: Execution ID from execution_history table
        db: PostgreSQLURLDatabase instance (required)
        stage: Stage number to filter (default: '01')

    Returns:
        Dict with:
            - input_tokens: Total input tokens used
            - output_tokens: Total output tokens used
            - cost_usd: Total cost in USD
    """
    if not db:
        logger.error("Database instance required for cost calculation")
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'cost_usd': 0.0
        }

    # Get execution timestamps from database
    try:
        execution = db.get_execution_by_id(execution_id)
        if not execution:
            logger.error(f"Execution #{execution_id} not found in database")
            return {
                'input_tokens': 0,
                'output_tokens': 0,
                'cost_usd': 0.0
            }

        started_at = execution.get('started_at')
        completed_at = execution.get('completed_at')

        if not started_at:
            logger.warning(f"Execution #{execution_id} has no started_at timestamp")
            return {
                'input_tokens': 0,
                'output_tokens': 0,
                'cost_usd': 0.0
            }

        # Parse timestamps and ensure they're timezone-aware
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))

        # Make naive datetimes aware (assume UTC)
        if started_at.tzinfo is None:
            from datetime import timezone
            started_at = started_at.replace(tzinfo=timezone.utc)
        if completed_at and completed_at.tzinfo is None:
            from datetime import timezone
            completed_at = completed_at.replace(tzinfo=timezone.utc)

        # If not completed yet, use current time
        if not completed_at:
            from datetime import timezone
            completed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Error fetching execution timestamps: {e}")
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'cost_usd': 0.0
        }

    try:
        usage = db.get_token_usage_between(
            stage=stage,
            start_ts=started_at,
            end_ts=completed_at,
            execution_id=execution_id
        )
        logger.info(f"Token costs for execution #{execution_id}: {(usage.get('input_tokens',0) + usage.get('output_tokens',0))} tokens, ${usage.get('cost_usd',0.0):.4f}")
        return {
            'input_tokens': int(usage.get('input_tokens', 0)),
            'output_tokens': int(usage.get('output_tokens', 0)),
            'cost_usd': round(float(usage.get('cost_usd', 0.0)), 4)
        }

    except Exception as e:
        logger.error(f"Error calculating costs: {e}")
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'cost_usd': 0.0
        }
