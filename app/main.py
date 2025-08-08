# main.py

"""
Main FastAPI application file. AI Agent system.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
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

# # --- Execution ---
# if __name__ == "__main__":
#     # Define the initial state for the invocation
#     initial_state = {
#         "original_request": "What is LangGraph and how does it compare to LangChain?",
#         "decomposed_tasks": [],
#         "action_history": [],
#         "final_result": None,
#         "next_agent": None
#     }

#     # Invoke the graph and stream the output
#     print("Invoking the Master Agent... \n")
#     final_state = app.invoke(initial_state)

#     print("\n--- Final Result ---")
#     # The final result is in the last completed task
#     final_answer = final_state['decomposed_tasks'][-1]['result']
#     print(final_answer)

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to the Otzar AI Gateway!"
    }