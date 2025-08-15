# /app/celery_worker.py
import os
from celery import Celery
from app.services import agent_service
from app.core.config import settings

# Initialize Celery, using Redis as the message broker.
celery_app = Celery(
    'tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)
celery_app.conf.update(
    task_track_started=True,
)

# This is the function from agent_service.py converted into a Celery task.
# The @celery_app.task decorator registers it with the Celery broker.
@celery_app.task
def run_agent_task(task_id, user_input, context_id):
    """
    The Celery task that executes the agent workflow.
    This runs on a separate worker process.
    """
    agent_service.start_agent_workflow(task_id, user_input, context_id)