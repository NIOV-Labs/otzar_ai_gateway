# main.py

"""
Main FastAPI application file. AI Agent system.
"""
import asyncio
import os
from pymongo import AsyncMongoClient
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db_client import db_client
from app.services.agent_service import get_agent_service
from app.services.result_ingestor import create_result_ingestor_service
from app.workers.agent_worker import create_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB Client
    mongo_client = AsyncMongoClient(settings.MONGO_URL)
    app.state.mongo_client = mongo_client
    print("--- MongoDB Client Initialized ---")

    agent_service = get_agent_service()
    app.state.agent_service = agent_service
    print("--- Agent Service Initialized ---")

    worker = create_worker()
    app.state.worker = worker
    worker_task = asyncio.create_task(worker.start())
    print("--- Agent Worker Started ---")

    result_ingestor = create_result_ingestor_service()
    app.state.result_ingestor = result_ingestor
    ingestor_task = asyncio.create_task(result_ingestor.start())
    print("--- Result Ingestor Started ---")

    yield # close can be async

    await app.state.mongo_client.close()
    print("--- MongoDB Client Closed ---")
    await app.state.agent_service.stop()
    print("--- Agent Service Closed ---")

    # Stop worker and ingestor
    worker_task.cancel()
    ingestor_task.cancel()
    print("--- Worker and Ingestor Stopped ---")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    lifespan=lifespan,
    # openapi_url="/api/v1/openapi.json",
    # docs_url="/api/v1/docs",
    # redoc_url="/api/v1/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to the Otzar AI Gateway!"
    }