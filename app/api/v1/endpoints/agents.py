"""
FastAPI endpoints for the Agent Service
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import logging

from app.services.agent_service import get_agent_service, AgentServiceError

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskCreateRequest(BaseModel):
    user_input: str = Field(..., description="The user's request or input")
    context_id: Optional[str] = Field(None, description="Optional context identifier")


class TaskResponse(BaseModel):
    conversation_id: str
    status: str
    user_input: str
    context_id: Optional[str] = None
    created_at: str
    updated_at: str
    result: Optional[str] = None
    error: Optional[str] = None


class StreamRequest(BaseModel):
    user_input: str = Field(..., description="The user's request for streaming")
    agent_name: str = Field("ResearchAgent", description="Name of the agent to use")


@router.post("/tasks", response_model=dict)
async def create_task(
    request: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    agent_service = Depends(get_agent_service)
):
    """Create a new agent task"""
    try:
        # Create the task
        conversation_id = await agent_service.create_new_task(
            user_input=request.user_input,
            context_id=request.context_id
        )
        
        # Start the workflow in the background
        background_tasks.add_task(
            agent_service.start_agent_workflow,
            conversation_id=conversation_id,
            user_input=request.user_input,
            context_id=request.context_id
        )
        
        return {
            "conversation_id": conversation_id,
            "status": "PENDING",
            "message": "Task created and workflow started"
        }
        
    except AgentServiceError as e:
        logger.error(f"Agent service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating task: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tasks/{conversation_id}", response_model=TaskResponse)
async def get_task(
    conversation_id: str,
    agent_service = Depends(get_agent_service)
):
    """Get task status and results"""
    try:
        task = await agent_service.get_task_status(conversation_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(**task)
        
    except AgentServiceError as e:
        logger.error(f"Agent service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting task: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    limit: int = 50,
    skip: int = 0,
    status: Optional[str] = None,
    agent_service = Depends(get_agent_service)
):
    """List tasks with optional filtering"""
    try:
        tasks = await agent_service.list_tasks(
            limit=limit,
            skip=skip,
            status_filter=status
        )
        
        return [TaskResponse(**task) for task in tasks]
        
    except AgentServiceError as e:
        logger.error(f"Agent service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ai-responses/{conversation_id}", response_model=List[Dict[str, Any]])
async def get_ai_responses(
    conversation_id: str,
    agent_service = Depends(get_agent_service)
):
    """Get all AI responses for a conversation"""
    try:
        # You'll need to add this method to the agent service
        responses = await agent_service.get_ai_responses(conversation_id)
        return responses
        
    except Exception as e:
        logger.error(f"Unexpected error getting AI responses: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/tasks/{conversation_id}")
async def cancel_task(
    conversation_id: str,
    agent_service = Depends(get_agent_service)
):
    """Cancel a running task"""
    try:
        cancelled = await agent_service.cancel_task(conversation_id)
        
        if not cancelled:
            raise HTTPException(
                status_code=400, 
                detail="Task not found or already completed"
            )
        
        return {"message": "Task cancelled successfully"}
        
    except AgentServiceError as e:
        logger.error(f"Agent service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error cancelling task: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stream")
async def stream_workflow(
    request: StreamRequest,
    agent_service = Depends(get_agent_service)
):
    """Stream agent workflow output"""
    try:
        return StreamingResponse(
            agent_service.stream_agent_workflow(
                user_input=request.user_input,
                agent_name=request.agent_name
            ),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
        
    except AgentServiceError as e:
        logger.error(f"Agent service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error streaming: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check(agent_service = Depends(get_agent_service)):
    """Health check endpoint"""
    try:
        health_status = await agent_service.health_check()
        
        if health_status["status"] != "healthy":
            raise HTTPException(status_code=503, detail=health_status)
        
        return health_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in health check: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@router.get("/health/worker")
async def worker_health():
    """Check worker health"""
    try:
        worker = get_agent_service().worker
        if worker:
            health = await worker.health_check()
            return health
        else:
            return {"status": "no_worker", "message": "Worker not initialized"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@router.get("/health/ingestor")
async def ingestor_health():
    """Check result ingestor health"""
    try:
        ingestor = get_agent_service().result_ingestor
        if ingestor:
            return {"status": "running", "message": "Result ingestor is running"}
        else:
            return {"status": "no_ingestor", "message": "Result ingestor not initialized"}
    except Exception as e:
        return {"status": "error", "error": str(e)}