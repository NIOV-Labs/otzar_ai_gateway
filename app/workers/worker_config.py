# app/workers/worker_config.py
"""
Configuration for Kafka Agent Workers
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class WorkerConfig:
    """Configuration for individual workers"""
    worker_id: Optional[str] = None
    max_concurrent_tasks: int = 5
    task_timeout_seconds: int = 300
    health_check_interval: int = 30
    restart_on_failure: bool = True
    max_retries: int = 3
    backoff_multiplier: float = 2.0


@dataclass
class KafkaConfig:
    """Kafka-specific configuration"""
    bootstrap_servers: str
    security_protocol: str = "SSL"
    ssl_cafile: Optional[str] = None
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    
    # Consumer settings
    consumer_group_id: str = "agent-worker-group"
    auto_offset_reset: str = "earliest"
    max_poll_records: int = 10
    session_timeout_ms: int = 30000
    
    # Producer settings
    compression_type: str = "gzip"
    linger_ms: int = 10
    batch_size: int = 16384


@dataclass
class AgentConfig:
    """Configuration for agent behavior"""
    enabled_agents: List[str] = None
    agent_timeout_seconds: int = 300
    max_memory_usage_mb: int = 512
    enable_async_execution: bool = True


class WorkerSettings:
    """Settings for the worker service"""
    
    def __init__(self):
        self.worker_config = WorkerConfig(
            max_concurrent_tasks=int(os.getenv("WORKER_MAX_CONCURRENT_TASKS", "5")),
            task_timeout_seconds=int(os.getenv("WORKER_TASK_TIMEOUT", "300")),
            health_check_interval=int(os.getenv("WORKER_HEALTH_CHECK_INTERVAL", "30")),
            restart_on_failure=os.getenv("WORKER_RESTART_ON_FAILURE", "true").lower() == "true",
            max_retries=int(os.getenv("WORKER_MAX_RETRIES", "3")),
        )
        
        self.kafka_config = KafkaConfig(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "SSL"),
            ssl_cafile=os.getenv("KAFKA_SSL_CAFILE"),
            ssl_certfile=os.getenv("KAFKA_SSL_CERTFILE"),
            ssl_keyfile=os.getenv("KAFKA_SSL_KEYFILE"),
            consumer_group_id=os.getenv("KAFKA_CONSUMER_GROUP", "agent-worker-group"),
            max_poll_records=int(os.getenv("KAFKA_MAX_POLL_RECORDS", "10")),
        )
        
        enabled_agents = os.getenv("ENABLED_AGENTS", "ResearchAgent,TranslatorAgent")
        self.agent_config = AgentConfig(
            enabled_agents=enabled_agents.split(",") if enabled_agents else [],
            agent_timeout_seconds=int(os.getenv("AGENT_TIMEOUT", "300")),
            max_memory_usage_mb=int(os.getenv("AGENT_MAX_MEMORY_MB", "512")),
            enable_async_execution=os.getenv("AGENT_ENABLE_ASYNC", "true").lower() == "true",
        )


# Global settings instance
worker_settings = WorkerSettings()
