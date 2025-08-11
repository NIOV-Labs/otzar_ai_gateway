"""
Service layer for initializing and running the agent workflow.
"""

import uuid
from langgraph.graph import StateGraph, END
from uuid import UUID
import json
from typing import Optional

from app.state.graph_state import MasterAgentState, AgentTask
from app.agents.child_agents.research_agent import ResearchAgent
from app.agents.master_agent import MasterAgent

# --- Database Simulation ---
# In a real application, this would be a connection to MongoDB.
# This in-memory dictionary simulates our persistent state storage.
TASK_STATE_DB = {}

# --- Configuration ---
# For robust observability with LangSmith.
# Ensure LANGCHAIN_API_KEY, etc., are set in your environment.
# os.environ["LANGCHAIN_TRACING_V2"] = "true" 

# --- Initialization ---
# We initialize the agents and compile the graph once to be reused across requests.
# 1. Instantiate Child Agents
research_agent = ResearchAgent()

# 2. Create the Agent Registry
# The Master Agent uses this to find and dispatch to child agents.
agent_registry = {
    research_agent.get_name(): research_agent
}

# 3. Instantiate the Master Agent with the registry
master_agent = MasterAgent(agent_registry)

# --- Graph Definition ---
# Define the workflow graph
workflow = StateGraph(MasterAgentState)

# Add the nodes to the graph
workflow.add_node("parse_user_request", master_agent.parse_user_request) 
workflow.add_node("delegate_task", master_agent.delegate_task)
workflow.add_node("execute_child_task", master_agent.execute_child_task)

# Set the entry point of the graph
workflow.set_entry_point("parse_user_request")

# Add edges to define the flow
workflow.add_edge("delegate_task", "execute_child_task")

# Add the conditional router
# After execution, the router decides if we are done or need another step.
# workflow.add_conditional_edges(
#     "execute_child_task",
#     master_agent.router,
#     {
#         "execute_child_task": "execute_child_task", # Loop back for more tasks
#         "end": END
#     }
# )
# For our simple one-shot case, we will just end after the first execution.

# Define the new flow
workflow.add_edge("parse_user_request", "delegate_task")
workflow.add_edge("delegate_task", "execute_child_task")
workflow.add_edge("execute_child_task", END)


# --- Compilation ---
# Compile the graph into a runnable application
app_graph = workflow.compile()


# --- Service Functions ---
def start_agent_workflow(task_id: UUID, user_input: str, context_id: Optional[str]):
    """
    The function that will be run in the background.
    It executes the agent graph and updates the state in our "DB".
    """
    print(f"[{task_id}] Agent workflow started.")
    
    # Set the initial state for the run
    initial_state = {
        "original_request": user_input,
        "context_id": context_id,
        "retrieved_context": None,
        "parsed_instructions": None,
        "decomposed_tasks": [],
        "action_history": [],
        "final_result": None,
        "next_agent": None
    }
    
    TASK_STATE_DB[task_id] = {
        "status": "RUNNING",
        "result": None,
        "error": None
    }
    
    try:
        # Invoke the graph. This is a blocking call.
        final_state = app_graph.invoke(initial_state)
        
        # Extract the final answer and update the state
        final_answer = final_state['decomposed_tasks'][-1]['result']
        TASK_STATE_DB[task_id].update({
            "status": "COMPLETED",
            "result": final_answer
        })
        print(f"[{task_id}] Agent workflow COMPLETED.")
    except Exception as e:
        print(f"[{task_id}] Agent workflow FAILED. Error: {e}")
        TASK_STATE_DB[task_id].update({
            "status": "FAILED",
            "error": str(e)
        })

def create_new_task(user_input: str) -> UUID:
    """Creates a new task ID and sets its initial state."""
    task_id = uuid.uuid4()
    TASK_STATE_DB[task_id] = {
        "status": "PENDING",
        "result": None,
        "error": None
    }
    return task_id

def get_task_status(task_id: UUID) -> dict:
    """Retrieves the status of a task from our 'DB'."""
    return TASK_STATE_DB.get(task_id, None)


async def stream_agent_workflow(user_input: str):
    """
    An async generator that streams the output of the research agent.
    """
    # For this direct streaming use case, we bypass the full graph 
    # and directly call our streaming-capable child agent.
    research_agent = agent_registry["ResearchAgent"]

    # We still create a task structure for consistency.
    task = AgentTask(
        task_id=uuid.uuid4(),
        task="Streaming Research Task",
        instructions=user_input,
        agent_name="ResearchAgent",
        status="RUNNING", # This is a transient task
        dependencies=[],
        result=None
    )

    try:
        # Iterate through the generator from the agent's stream_task method..
        async for content_chunk in research_agent.stream_task(task):
            # Format the chunk according to the SSE specification:
            # "data: {your_data}\n\n"
            data_to_send = json.dumps({"token": content_chunk})
            yield f"data: {data_to_send}\n\n"


        # Once the stream is complete, send a special [DONE] message
        # The client will use this to close the connection.
        done_message = json.dumps({"token": "[DONE]"})
        yield f"data: {done_message}\n\n"    

    except Exception as e:
        print(f"Error streaming agent workflow: {e}")
        error_message = json.dumps({"token": f"Error: {str(e)}"})
        yield f"data: {error_message}\n\n"