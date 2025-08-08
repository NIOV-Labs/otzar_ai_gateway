# /agents/master_agent.py

"""
Defines the graph-based Master Agent for orchestrating child agents.
"""
import uuid
from typing import Dict
from app.state.graph_state import MasterAgentState, AgentTask
from app.protocols.a2a_interface import AgentInterface

class MasterAgent:
    """
    Represents the Master Agent's workflow, defined as a graph.
    This class holds the logic for the nodes in the LangGraph.
    """

    def __init__(self, agent_registry: Dict[str, AgentInterface]):
        """
        Initializes the MasterAgent with a registry of available child agents.
        
        Args:
            agent_registry: A dictionary mapping agent names to agent instances.
        """
        self.agent_registry = agent_registry

    def delegate_task(self, state: MasterAgentState) -> MasterAgentState:
        """
        This is the entry node. It decomposes the user request into the first task.
        
        Note: For this initial version, we will do a simple 1:1 delegation.
        A more advanced version would involve more complex decomposition logic.
        """
        print("--- MasterAgent: Delegating task ---")
        original_request = state['original_request']
        
        # Simple routing: For now, we assume all tasks go to the ResearchAgent.
        # An advanced router would use an LLM call to select the best agent.
        agent_name = "ResearchAgent"

        task = AgentTask(
            task_id=uuid.uuid4(),
            task="Initial Research Task",
            instructions=original_request,
            agent_name=agent_name,
            status="pending",
            dependencies=[],
            result=None
        )
        
        state['decomposed_tasks'].append(task)
        state['next_agent'] = agent_name
        return state

    def execute_child_task(self, state: MasterAgentState) -> MasterAgentState:
        """
        Executes the task assigned to the next agent.
        """
        print(f"--- MasterAgent: Executing child task ---")
        # Find the pending task for the next agent
        task_to_execute = next(
            (t for t in state['decomposed_tasks'] if t['status'] == 'pending' and t['agent_name'] == state['next_agent']),
            None
        )
        
        if not task_to_execute:
            print("--- MasterAgent: No pending task found. Ending. ---")
            state['next_agent'] = "end"
            return state

        # Retrieve the agent from the registry
        agent = self.agent_registry[task_to_execute['agent_name']]
        
        # Execute the task (this is our in-memory A2A call)
        result = agent.execute_task(task_to_execute)
        
        # Update the state with the result
        for task in state['decomposed_tasks']:
            if task['task_id'] == task_to_execute['task_id']:
                task['status'] = 'completed'
                task['result'] = result
                break
        
        # For now, we assume one task and then we are done.
        state['next_agent'] = "end"
        return state

    def router(self, state: MasterAgentState) -> str:
        """
        The conditional router that determines the next step.
        """
        print(f"--- MasterAgent: Routing ---")
        if state['next_agent'] == "end":
            return "end"
        else:
            return "execute_child_task"