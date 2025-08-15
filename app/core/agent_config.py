"""
Configuration for the Agent Service
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Configuration for individual agents"""
    name: str
    enabled: bool = True
    max_concurrent_tasks: int = 5
    timeout_seconds: int = 300
    retry_attempts: int = 3
    streaming_supported: bool = False
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass 
class WorkflowConfig:
    """Configuration for the workflow service"""
    max_concurrent_workflows: int = 10
    default_timeout_seconds: int = 600
    enable_streaming: bool = True
    enable_checkpointing: bool = True
    health_check_interval: int = 60
    task_cleanup_days: int = 30


class AgentServiceSettings:
    """Settings for the Agent Service"""
    
    def __init__(self):
        self.workflow_config = WorkflowConfig(
            max_concurrent_workflows=int(os.getenv("MAX_CONCURRENT_WORKFLOWS", "10")),
            default_timeout_seconds=int(os.getenv("DEFAULT_WORKFLOW_TIMEOUT", "600")),
            enable_streaming=os.getenv("ENABLE_STREAMING", "true").lower() == "true",
            enable_checkpointing=os.getenv("ENABLE_CHECKPOINTING", "true").lower() == "true",
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "60")),
            task_cleanup_days=int(os.getenv("TASK_CLEANUP_DAYS", "30"))
        )
        
        self.agent_configs = {
            "ResearchAgent": AgentConfig(
                name="ResearchAgent",
                enabled=os.getenv("RESEARCH_AGENT_ENABLED", "true").lower() == "true",
                max_concurrent_tasks=int(os.getenv("RESEARCH_AGENT_MAX_TASKS", "5")),
                timeout_seconds=int(os.getenv("RESEARCH_AGENT_TIMEOUT", "300")),
                streaming_supported=True
            ),
            "TranslatorAgent": AgentConfig(
                name="TranslatorAgent", 
                enabled=os.getenv("TRANSLATOR_AGENT_ENABLED", "true").lower() == "true",
                max_concurrent_tasks=int(os.getenv("TRANSLATOR_AGENT_MAX_TASKS", "3")),
                timeout_seconds=int(os.getenv("TRANSLATOR_AGENT_TIMEOUT", "180")),
                streaming_supported=False
            )
        }
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent"""
        return self.agent_configs.get(agent_name)
    
    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled"""
        config = self.get_agent_config(agent_name)
        return config.enabled if config else False


# Global settings instance
agent_settings = AgentServiceSettings()
