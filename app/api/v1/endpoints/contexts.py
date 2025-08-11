from fastapi import APIRouter, status, HTTPException
from app.api.v1.schemas.context import ContextCreationRequest
from app.services.context_service import get_context, create_context

router = APIRouter()

@router.post("/contexts", status_code=status.HTTP_201_CREATED, tags=["Context"])
def add_new_context(request: ContextCreationRequest):
    try:
        create_context(**request.model_dump())
        return {"message": f"Context '{request.context_id}' created successfully."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("/contexts/{context_id}", tags=["Context"])
def get_a_context(context_id: str):
    context = get_context(context_id)
    if not context:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Context not found")
    return context
