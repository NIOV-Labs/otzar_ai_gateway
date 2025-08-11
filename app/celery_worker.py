# /app/celery_worker.py
import os
from celery import Celery
from app.services import agent_service

# Initialize Celery, using Redis as the message broker.
celery_app = Celery(
    'tasks',
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
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