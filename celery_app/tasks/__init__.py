# Celery tasks
# Importar todas las tareas para que Celery las descubra automáticamente
from celery_app.tasks.stage01_tasks import execute_stage01_task
from celery_app.tasks.scheduler_tasks import process_scheduled_executions_task
from celery_app.tasks.newsletter_tasks import execute_newsletter_pipeline_task

__all__ = ['execute_stage01_task', 'process_scheduled_executions_task', 'execute_newsletter_pipeline_task']
