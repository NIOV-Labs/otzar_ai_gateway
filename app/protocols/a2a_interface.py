# /protocols/a2a_interface.py

"""
Defines the abstract interface for Agent-to-Agent (A2A) communication.

This module provides a standardized contract for how agents in the system
interact. By adhering to this interface, we ensure that communication is
consistent and the system is modular.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from state.graph_state import AgentTask

class AgentInterface(ABC):
    """
    An abstract base class that all agents in the system must implement.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Returns the unique name of the agent."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, str]:
        """
        Returns a dictionary describing the agent's capabilities.
        e.g., {"tool_name": "description of what the tool does"}
        """
        pass

    @abstractmethod
    def execute_task(self, task: AgentTask) -> Any:
        """
        The primary entry point for an agent to perform a task.

        Args:
            task: An AgentTask object containing all necessary information.

        Returns:
            The result of the task execution.
        """
        pass