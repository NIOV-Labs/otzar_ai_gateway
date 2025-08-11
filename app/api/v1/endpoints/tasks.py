"""
Defines the API endpoints for the agent service.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status 
from fastapi.responses import StreamingResponse
from uuid import UUID

from app.api.v1.schemas.task import TaskCreationRequest, TaskCreationResponse, TaskStatusResponse
from app.services import agent_service

router = APIRouter()

@router.post(
    "", 
    response_model=TaskCreationResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def create_task(
    request: TaskCreationRequest,
    background_tasks: BackgroundTasks
):
    """
    Create a new agent task and run it in the background.
    """
    try:
        task_id = agent_service.create_new_task(request.input)

        # Add the long-running agent workflow to the background tasks
        background_tasks.add_task(
            agent_service.start_agent_workflow,
            task_id, 
            request.input,
            request.context_id
        )
        
        return TaskCreationResponse(task_id=task_id, status="PENDING")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/stream", tags=["tasks"])
def stream_task(query: str):
    """
    Creates and streams the result of an agent task in real-time
    using Server-Sent Events (SSE).

    To use, connect to this endpoint with a client that supports SSE,
    for example, the JavaScript `EventSource` API.
    """

    return StreamingResponse(
        agent_service.stream_agent_workflow(query),
        media_type="text/event-stream"
    )


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_200_OK
)
def get_task(task_id: UUID):
    """
     Retrieve the status and result of an agent task.
    """
    try:
        task = agent_service.get_task_status(task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with ID {task_id} not found."
            )

        return TaskStatusResponse(
            task_id=task_id,
            # status=task["status"],
            **task 
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )