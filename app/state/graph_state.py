# /state/graph_state.py

"""
Defines the state graph for the multi-agent system.

This module contains the core data structures that represent the state of 
our agentic workflow. The state is managed by LangGraph and is passed
between nodes (agents and tools) during execution. It is designed to be
serializable, robust, and easily debuggable.
"""

from typing import TypedDict, List, Dict, Any, Optional
from uuid import UUID

class AgentTask(TypedDict):
    """
    Represents a single task to be executed by a child agent.
    
    This structure is created by the Master Agent when it decomposes a
    complex problem.
    """
    task_id: UUID       # Unique identifier for the task
    task: str           # The natural language description of the task
    instructions: str   # Specific instructions for the agent
    agent_name: str     # The designated agent to handle the task
    status: str         # e.g., "pending", "in_progress", "completed", "failed"
    dependencies: List[UUID] # List of task_ids this task depends on
    result: Optional[str] # The output from the agent upon completion

class MasterAgentState(TypedDict):
    """
    The complete state graph for the Master AI Agent system.

    This dictionary is the central object that flows through the LangGraph.
    It's append-only for history tracking, ensuring we have a full audit
    trail of the agent's reasoning process.
    """
    original_request: str               # The initial request from the user
    decomposed_tasks: List[AgentTask]   # The list of tasks delegated to child agents
    
    # A log of all actions taken by all agents, for full traceability.
    action_history: List[Dict[str, Any]] 
    
    # The final, synthesized result to be presented to the user.
    final_result: Optional[str]
    
    # Tracks which agent is currently acting
    next_agent: str