# /app/services/context_service.py
"""
Service for managing the Context Store in MongoDB.
"""
import asyncio
from app.core.db_client import db_client

# Global collection reference
_collection = None

async def _get_collection():
    """Get the contexts collection, ensuring connection"""
    global _collection
    if _collection is None:
        if not db_client.is_connected():
            await db_client.connect()
        _collection = await db_client.get_collection("contexts")
    return _collection

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

async def get_context(context_id: str) -> dict | None:
    """Fetch a context by ID from MongoDB"""
    print(f"--- ContextService: Fetching context for '{context_id}' ---")
    collection = await _get_collection()
    return await collection.find_one({"context_id": context_id})

async def create_context(context_id: str, description: str, content: str):
    """Create a new context in MongoDB"""
    print(f"--- ContextService: Creating context '{context_id}' ---")
    existing = await get_context(context_id)
    if existing:
        raise ValueError("Context ID already exists.")

    collection = await _get_collection()
    await collection.insert_one({
        "context_id": context_id,
        "description": description,
        "content": content
    })

async def update_context(context_id: str, description: str = None, content: str = None):
    """Update an existing context in MongoDB"""
    print(f"--- ContextService: Updating context '{context_id}' ---")
    collection = await _get_collection()
    
    update_data = {}
    if description is not None:
        update_data["description"] = description
    if content is not None:
        update_data["content"] = content
    
    if not update_data:
        raise ValueError("No data provided to update")
    
    result = await collection.update_one(
        {"context_id": context_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise ValueError("Context ID not found")

async def delete_context(context_id: str):
    """Delete a context from MongoDB"""
    print(f"--- ContextService: Deleting context '{context_id}' ---")
    collection = await _get_collection()
    
    result = await collection.delete_one({"context_id": context_id})
    
    if result.deleted_count == 0:
        raise ValueError("Context ID not found")

async def list_contexts():
    """List all contexts from MongoDB"""
    print("--- ContextService: Listing all contexts ---")
    collection = await _get_collection()
    
    contexts = []
    async for doc in collection.find({}):
        contexts.append({
            "context_id": doc["context_id"],
            "description": doc["description"],
            "content": doc["content"]
        })
    
    return contexts