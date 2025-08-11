from pydantic import BaseModel
from typing import Optional

class ContextCreationRequest(BaseModel):
    context_id: str
    description: str
    content: str

class ParsedInstructions(BaseModel):
    """The structured output from the Instruction Parser agent."""
    core_task: str
    persona: Optional[str] = "a helpful AI assistant"
    format_instructions: Optional[str] = "Provide a clear, well-structured response."
    constraints: Optional[str] = "None"
