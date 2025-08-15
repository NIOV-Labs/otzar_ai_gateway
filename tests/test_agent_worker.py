"""
Tests for the Agent Worker Service
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.workers.agent_worker import KafkaAgentWorker, WorkerPool


@pytest.fixture
async def mock_worker():
    """Create a mock worker for testing"""
    worker = KafkaAgentWorker(worker_id="test-worker")
    
    # Mock Kafka components
    worker.consumer = AsyncMock()
    worker.producer = AsyncMock()
    worker.available_agents = {
        "TestAgent": MagicMock()
    }
    worker._initialized = True
    
    return worker


@pytest.mark.asyncio
async def test_worker_initialization():
    """Test worker initialization"""
    worker = KafkaAgentWorker(worker_id="test-worker")
    
    with patch.object(worker, '_initialize_agents'), \
         patch.object(worker, '_setup_kafka_consumer'), \
         patch.object(worker, '_setup_kafka_producer'):
        
        await worker.initialize()
        assert worker._initialized is True


@pytest.mark.asyncio
async def test_task_processing_success(mock_worker):
    """Test successful task processing"""
    task_data = {
        "task_id": "test-task-1",
        "agent_name": "TestAgent",
        "conversation_id": "test-conv-1",
        "instructions": "Test task"
    }
    
    # Mock agent execution
    mock_agent = mock_worker.available_agents["TestAgent"]
    mock_agent.execute_task.return_value = "Task completed successfully"
    
    result = await mock_worker._process_task(task_data)
    
    assert result is True
    assert mock_worker._tasks_processed == 1
    assert mock_worker._tasks_failed == 0


@pytest.mark.asyncio
async def test_task_processing_failure(mock_worker):
    """Test task processing failure"""
    task_data = {
        "task_id": "test-task-2",
        "agent_name": "TestAgent",
        "conversation_id": "test-conv-2",
        "instructions": "Test task"
    }
    
    # Mock agent execution failure
    mock_agent = mock_worker.available_agents["TestAgent"]
    mock_agent.execute_task.side_effect = Exception("Task failed")
    
    result = await mock_worker._process_task(task_data)
    
    assert result is False
    assert mock_worker._tasks_processed == 0
    assert mock_worker._tasks_failed == 1


@pytest.mark.asyncio
async def test_unknown_agent_handling(mock_worker):
    """Test handling of unknown agent tasks"""
    task_data = {
        "task_id": "test-task-3",
        "agent_name": "UnknownAgent",
        "conversation_id": "test-conv-3",
        "instructions": "Test task"
    }
    
    result = await mock_worker._process_task(task_data)
    
    # Should return True (not an error, just ignored)
    assert result is True
    assert mock_worker._tasks_processed == 0
    assert mock_worker._tasks_failed == 0


@pytest.mark.asyncio
async def test_worker_health_check(mock_worker):
    """Test worker health check"""
    health = await mock_worker.health_check()
    
    assert health["status"] == "stopped"  # Not running in test
    assert health["worker_id"] == "test-worker"
    assert "agents_loaded" in health
    assert "tasks_processed" in health


@pytest.mark.asyncio
async def test_worker_pool():
    """Test worker pool functionality"""
    with patch('app.workers.agent_worker.KafkaAgentWorker') as MockWorker:
        mock_instances = [AsyncMock() for _ in range(3)]
        MockWorker.side_effect = mock_instances
        
        pool = WorkerPool(num_workers=3)
        
        # Mock the start method to avoid actual Kafka connections
        for mock_instance in mock_instances:
            mock_instance.start = AsyncMock()
        
        # This would normally start workers, but we're mocking
        assert pool.num_workers == 3
        assert len(pool.workers) == 0  # Not started yet


if __name__ == "__main__":
    pytest.main([__file__])