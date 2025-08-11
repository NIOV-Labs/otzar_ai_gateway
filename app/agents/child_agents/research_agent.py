# /agents/child_agents/research_agent.py

"""
Implements the ResearchAgent, a specialized child agent for web research.
"""

from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_tool_calling_agent
from typing import Dict, Any

from app.core.config import settings
from app.protocols.a2a_interface import AgentInterface
from app.state.graph_state import AgentTask
from app.tools.web_search import get_web_search_tool

# It is best practice to configure the LLM centrally, but for this example,
# we will instantiate it directly. Ensure OPENAI_API_KEY is set in your environment.
# from config import settings; llm = ChatOpenAI(api_key=settings.OPENAI_API_KEY)

class ResearchAgent(AgentInterface):
    """
    A specialized agent that performs web searches to answer questions.
    """

    def __init__(self):
        """
        Initializes the ResearchAgent with its LLM, tools, and prompt.
        """
        # 1. The LLM: The "brain" of the agent.
        self.llm = AzureChatOpenAI(
            model=settings.AZURE_OPENAI_MODEL, 
            temperature=0,
            api_key=settings.AZURE_OPENAI_API_KEY,
            openai_api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_API_BASE,
            azure_deployment=settings.AZURE_35_TURBO_DEPLOYMENT_NAME,
            )

        # 2. Scoped Tools: This agent ONLY gets the web search tool.
        self.tools = [get_web_search_tool()]

        # 3. The System Prompt (The "Constitution"): Defines the agent's role and constraints.
        system_prompt = (
            "You are a world-class Research Assistant agent. Your sole purpose is to "
            "find and synthesize information from the internet using your available tools. "
            "You MUST NOT give personal opinions or engage in conversation. "
            "You must only answer the direct question based on the research you conduct."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        # 4. The Agent Core: Binds the LLM, tools, and prompt together.
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        
        # 5. The Executor: The runtime that actually executes the agent's logic.
        self.agent_executor = AgentExecutor(
            agent=agent, 
            tools=self.tools, 
            verbose=True  # Set to True for detailed logging of agent's thoughts
        )

    def get_name(self) -> str:
        """Returns the unique name of the agent."""
        return "ResearchAgent"

    def get_capabilities(self) -> Dict[str, str]:
        """Returns a dictionary describing the agent's capabilities."""
        return {
            tool.name: tool.description for tool in self.tools
        }

    def execute_task(self, task: AgentTask) -> Any:
        """
        Executes a research task.

        This method is the entry point for the master agent to delegate work.
        """
        print(f"--- ResearchAgent received task: {task['instructions']} ---")
        result = self.agent_executor.invoke({
            "input": task['instructions']
        })
        return result['output']

    async def stream_task(self, task: AgentTask) -> Any:
        """
        Executes a research task and streams the output chunks.

        This method is an async generator that yields data as it's produced
        by the agent's thought process.
        """
        # print(f"--- ResearchAgent starting stream for task: {task.instructions} ---")
        print(f"--- ResearchAgent starting stream for task: {task['instructions']} ---")

        # .stream() returns a generator of response chunks
        # async for chunk in self.agent_executor.astream({"input": task.instructions}):
        async for chunk in self.agent_executor.astream({"input": task['instructions']}):
            # AgentExecutor chunks are dictionaries. We are interested in the content
            # of the AIMessageChunk, which represents the LLM's output.
            if "messages" in chunk:
                # The 'messages' key contains a list of BaseMessageChunk objects.
                for message_chunk in chunk["messages"]:
                    # We only care about the AI's response content
                    if message_chunk.content:
                        # Yield the content part of the chunk
                        yield message_chunk.content
                        print(f"--- ResearchAgent: Streamed chunk: {message_chunk.content} ---")
                        print(message_chunk)
                        print(chunk)