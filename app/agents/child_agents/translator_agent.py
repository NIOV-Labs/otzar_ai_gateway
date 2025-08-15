"""
Implements the TranslatorAgent, a specialized agent for language translation.
"""

from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from typing import Dict, Any

from app.core.config import settings
from app.protocols.a2a_interface import AgentInterface
from app.state.graph_state import AgentTask

class TranslatorAgent(AgentInterface):
    """
    A specialized agent that translates text from a source language to a
    target language as specified in the user's instructions.
    """

    def __init__(self):
        """
        Initializes the TranslatorAgent. This agent uses a direct LLM call
        with a specialized prompt for its core logic.
        """
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            azure_deployment=settings.AZURE_OPENAI_MODEL,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

        # This agent's "tool" is a highly-specific prompt chain.
        system_prompt = (
            "You are a highly skilled, professional language translator. Your sole purpose is to "
            "translate the text provided by the user. First, identify the target language from the "
            "user's request. Then, translate the core text to that target language. "
            "You MUST NOT answer questions, provide explanations, or do anything other than translate. "
            "Your final output must ONLY be the translated text and nothing else."
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}")
        ])

        # The chain that forms the agent's core logic
        self.translate_chain = prompt | self.llm | StrOutputParser()

    def get_name(self) -> str:
        """
        Returns the name of the agent.
        """
        return "TranslatorAgent"

    def get_capabilities(self) -> str:
        """
        Returns a string describing the agent's capabilities.
        This description is crucial for the router to make a good decision.
        """
        return (
            "An expert language translator. Use this agent for any requests that involve "
            "translating text from one language to another, such as 'translate this to Spanish' "
            "or 'how do you say hello in Japanese'."
        )
    
    def execute_task(self, task: AgentTask) -> Any:
        """
        Executes the agent's core logic.
        """
        print(f"TranslatorAgent received task: {task["instructions"]}")
        result = self.translate_chain.invoke({
            "input": task["instructions"]
        })

        return result

    async def stream_task(self, task: AgentTask):
        """
        Streams the agent's output as it executes the task.
        """
        result = self.execute_task(task)
        yield result