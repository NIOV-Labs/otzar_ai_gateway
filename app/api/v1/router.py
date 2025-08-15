from app.monitoring.worker_dashboard import router as monitoring_router
from fastapi import APIRouter
from app.api.v1.endpoints import agents, tasks

api_router = APIRouter()

api_router.include_router(tasks.router, prefix="/tasks")
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])