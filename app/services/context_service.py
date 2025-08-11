# /app/services/context_service.py
"""
Service for managing the Context Store in MongoDB.
For now, we'll simulate it with a dictionary.
"""

# --- Database Simulation ---
# In a real app, this would use a Motor (async MongoDB) client.
CONTEXT_DB = {
    "CorporateStyleGuide": {
        "description": "The official tone and style guide for all corporate communications.",
        "content": "Communication should be formal, data-driven, and avoid speculative language. Use the 'inverted pyramid' structure for summaries."
    },
    "CodeGenerationPolicy": {
        "description": "Policy for generating code within the system.",
        "content": "All generated Python code must be PEP8 compliant, include docstrings for all public functions, and must not use external libraries unless explicitly approved."
    }
}

def get_context(context_id: str) -> dict | None:
    print(f"--- ContextService: Fetching context for '{context_id}' ---")
    return CONTEXT_DB.get(context_id)

def create_context(context_id: str, description: str, content: str):
    print(f"--- ContextService: Creating context '{context_id}' ---")
    if context_id in CONTEXT_DB:
        raise ValueError("Context ID already exists.")
    CONTEXT_DB[context_id] = {"description": description, "content": content}
    return CONTEXT_DB[context_id]