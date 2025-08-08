
"""
Pydantic schemas for API request and response validation.
"""
from pydantic import BaseModel
from typing import Optional, Any, Literal
from uuid import UUID

class TaskCreationRequest(BaseModel):
    """The request model for creating a new agent task."""
    input: str
    
class TaskCreationResponse(BaseModel):
    """The response model after successfully creating a task."""
    task_id: UUID
    status: str

class TaskStatusResponse(BaseModel):
    """The response model for checking the status of a task."""
    task_id: UUID
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    result: Optional[Any] = None
    error: Optional[str] = None