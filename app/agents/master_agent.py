# /agents/master_agent.py

"""
Defines the graph-based Master Agent for orchestrating child agents.
"""
import uuid
from typing import Dict
from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from app.core.config import settings
from app.state.graph_state import MasterAgentState, AgentTask
from app.protocols.a2a_interface import AgentInterface
from app.api.v1.schemas.context import ParsedInstructions
from app.services.context_service import get_context

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
        # The "Meta Agent" for parsing instructions
        self.instruction_parser = AzureChatOpenAI(
            model=settings.AZURE_OPENAI_03_MINI_DEPLOYMENT_NAME,
            temperature=0,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-15",
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        ).with_structured_output(ParsedInstructions)
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at deconstructing user requests into actionable components. Analyze the user's input and extract the core task, any specified persona, formatting requirements, and constraints. Do not attempt to answer the user's request, only parse it."),
            ("human", "User Request", "{input}"),
        ])
        self.parser_chain = self.prompt_template | self.instruction_parser

    def parse_user_request(self, state: MasterAgentState) -> MasterAgentState:
        """NEW ENTRY NODE: Parses the user request and fetches context."""
        print("--- MasterAgent: Parsing user request ---")
        request = state['original_request']
        context_id = state['context_id']

        # Parse instructions
        parsed_instructions = self.parser_chain.invoke({"input": request})
        state['parsed_instructions'] = parsed_instructions

        # Retrieve context if requested
        if context_id:
            context = get_context(context_id)
            if context:
                state['received_context'] = context['content']
                print(f"--- MasterAgent: Successfully retrieved context '{context_id}' ---")

        return state


    def delegate_task(self, state: MasterAgentState) -> MasterAgentState:
        """
        This is the entry node. It decomposes the user request into the first task.
        
        Note: For this initial version, we will do a simple 1:1 delegation.
        A more advanced version would involve more complex decomposition logic.
        """
        print("--- MasterAgent: Delegating task with dynamic prompt ---")
        # For now, we still route to ResearchAgent. A smarter router could use
        # the parsed_instructions to choose an agent.

        agent_name = "ResearchAgent"

        # --- DYNAMIC PROMPT ASSEMBLY ---
        parsed = state['parsed_instructions']
        final_instructions_for_agent = (
            f"Here is the core task you must complete: {parsed.core_task}.\n\n"
            f"Adhere to the following persona: {parsed.persona}.\n"
            f"Follow these formatting requirements: {parsed.format_instructions}.\n"
            f"Obey these constraints: {parsed.constraints}.\n"
        )

        # Add the retrieved context, if it exists, to the instructions.
        if state.get('received_context'):
            final_instructions_for_agent += (
                "\n--- IMPORTANT CONTEXT TO USE ---\n"
                f"{state['received_context']}\n"
                "--- END OF CONTEXT ---\n"
            )

        # Create the task

        task = AgentTask(
            task_id=uuid.uuid4(),
            task=f"Dynamically Assembled Research Task",
            instructions=final_instructions_for_agent,
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