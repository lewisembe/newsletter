"""
Celery application for newsletter pipeline tasks.
"""
from celery import Celery
import os

# Create Celery app
celery = Celery('newsletter_tasks')

# Configuration
celery.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/1')
celery.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/2')

# Task configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=int(os.getenv('CELERY_TASK_TIME_LIMIT', '3600')),  # 1 hour
    task_soft_time_limit=int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '3300')),  # 55 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24 hours
    task_routes={
        'execute_stage01': {'queue': 'stage01'},
        'execute_newsletter_pipeline': {'queue': 'newsletters'},
        'process_scheduled_executions': {'queue': 'scheduler'},
    },
    beat_schedule={
        'process-scheduled-executions': {
            'task': 'process_scheduled_executions',
            'schedule': 60.0,  # Every minute
        },
    },
)

# Auto-discover tasks
celery.autodiscover_tasks(['celery_app.tasks'])

# Export for imports
celery_app = celery
