from datetime import datetime, timezone
import uuid
import pickle
import asyncio
from typing import List, Optional, Any, AsyncGenerator, Dict, Union

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointTuple
from collections import deque

from app.core.db_client import db_client

# WARNING: Pickling is insecure. In a production environment with untrusted data,
# you should use a safer serialization format like JSON with Pydantic models.
# For this trusted, internal system, pickle is used for its ability to serialize
# complex Python objects, which is required by LangGraph's default state.

class DequeCheckpoint:
    """
    Enhanced checkpoint wrapper that provides deque-based functionality
    for efficient state management and history tracking.
    """
    
    def __init__(self, 
                 data: Any, 
                 max_history_size: int = 100,
                 max_task_queue_size: int = 50,
                 enable_circular_buffer: bool = True):
        self.data = data
        self.timestamp = datetime.now(timezone.utc)
        self.checkpoint_id = str(uuid.uuid4())
        self.max_history_size = max_history_size
        self.max_task_queue_size = max_task_queue_size
        self.enable_circular_buffer = enable_circular_buffer
        
        # Initialize deque-based structures if data is a dict with specific keys
        if isinstance(data, dict):
            self._initialize_deque_structures(data)

    def _initialize_deque_structures(self, data: Dict[str, Any]):
        """Initialize deque-based structures for efficient state management"""
        
        # Convert action_history to deque for circular buffer behavior
        if 'action_history' in data and not isinstance(data['action_history'], deque):
            if self.enable_circular_buffer:
                data['action_history'] = deque(
                    data['action_history'], 
                    maxlen=self.max_history_size
                )
            else:
                data['action_history'] = deque(data['action_history'])
        
        # Convert decomposed_tasks to deque for efficient task management
        if 'decomposed_tasks' in data and not isinstance(data['decomposed_tasks'], deque):
            if self.enable_circular_buffer:
                data['decomposed_tasks'] = deque(
                    data['decomposed_tasks'], 
                    maxlen=self.max_task_queue_size
                )
            else:
                data['decomposed_tasks'] = deque(data['decomposed_tasks'])
        
        # Convert child_results to deque if it exists
        if 'child_results' in data and not isinstance(data['child_results'], deque):
            if self.enable_circular_buffer:
                data['child_results'] = deque(
                    data['child_results'], 
                    maxlen=self.max_task_queue_size
                )
            else:
                data['child_results'] = deque(data['child_results']) 

    def add_action(self, action: Dict[str, Any]):
        """Add an action to the history with automatic circular buffer management"""
        if isinstance(self.data, dict) and 'action_history' in self.data:
            if not isinstance(self.data['action_history'], deque):
                self.data['action_history'] = deque(maxlen=self.max_history_size)
            
            action_with_timestamp = {
                **action,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'checkpoint_id': self.checkpoint_id
            }
            self.data['action_history'].append(action_with_timestamp)
    
    def add_task(self, task: Dict[str, Any]):
        """Add a task to the decomposed_tasks queue"""
        if isinstance(self.data, dict) and 'decomposed_tasks' in self.data:
            if not isinstance(self.data['decomposed_tasks'], deque):
                self.data['decomposed_tasks'] = deque(maxlen=self.max_task_queue_size)
            
            task_with_timestamp = {
                **task,
                'added_at': datetime.now(timezone.utc).isoformat(),
                'checkpoint_id': self.checkpoint_id
            }
            self.data['decomposed_tasks'].append(task_with_timestamp)

    def add_child_result(self, result: Dict[str, Any]):
        """Add a child agent result to the results queue"""
        if isinstance(self.data, dict) and 'child_results' in self.data:
            if not isinstance(self.data['child_results'], deque):
                self.data['child_results'] = deque(maxlen=self.max_task_queue_size)
            
            result_with_timestamp = {
                **result,
                'received_at': datetime.now(timezone.utc).isoformat(),
                'checkpoint_id': self.checkpoint_id
            }
            self.data['child_results'].append(result_with_timestamp)
    
    def get_recent_actions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent actions from history"""
        if isinstance(self.data, dict) and 'action_history' in self.data:
            history = self.data['action_history']
            if isinstance(history, deque):
                return list(history)[-count:]
            return history[-count:] if len(history) > count else history
        return []
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks"""
        if isinstance(self.data, dict) and 'decomposed_tasks' in self.data:
            tasks = self.data['decomposed_tasks']
            if isinstance(tasks, deque):
                return [task for task in tasks if task.get('status') == 'pending']
            return [task for task in tasks if task.get('status') == 'pending']
        return []

    def get_completed_tasks(self) -> List[Dict[str, Any]]:
        """Get all completed tasks"""
        if isinstance(self.data, dict) and 'decomposed_tasks' in self.data:
            tasks = self.data['decomposed_tasks']
            if isinstance(tasks, deque):
                return [task for task in tasks if task.get('status') == 'completed']
            return [task for task in tasks if task.get('status') == 'completed']
        return []

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the current state"""
        if not isinstance(self.data, dict):
            return {'data_type': type(self.data).__name__}
        
        summary = {
            'checkpoint_id': self.checkpoint_id,
            'timestamp': self.timestamp.isoformat(),
            'has_original_request': 'original_request' in self.data,
            'has_parsed_instructions': 'parsed_instructions' in self.data,
            'next_agent': self.data.get('next_agent'),
            'final_result': self.data.get('final_result') is not None
        }
        
        # Add counts for deque-based structures
        if 'action_history' in self.data:
            history = self.data['action_history']
            summary['action_history_count'] = len(history)
            if isinstance(history, deque):
                summary['action_history_maxlen'] = history.maxlen
        
        if 'decomposed_tasks' in self.data:
            tasks = self.data['decomposed_tasks']
            summary['total_tasks'] = len(tasks)
            summary['pending_tasks'] = len([t for t in tasks if t.get('status') == 'pending'])
            summary['completed_tasks'] = len([t for t in tasks if t.get('status') == 'completed'])
            if isinstance(tasks, deque):
                summary['tasks_maxlen'] = tasks.maxlen
        
        if 'child_results' in self.data:
            results = self.data['child_results']
            summary['child_results_count'] = len(results)
            if isinstance(results, deque):
                summary['child_results_maxlen'] = results.maxlen
        
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'checkpoint_id': self.checkpoint_id,
            'max_history_size': self.max_history_size,
            'max_task_queue_size': self.max_task_queue_size,
            'enable_circular_buffer': self.enable_circular_buffer
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DequeCheckpoint':
        """Create from dictionary"""
        checkpoint = cls(data['data'])
        checkpoint.timestamp = datetime.fromisoformat(data['timestamp'])
        checkpoint.checkpoint_id = data['checkpoint_id']
        checkpoint.max_history_size = data.get('max_history_size', 100)
        checkpoint.max_task_queue_size = data.get('max_task_queue_size', 50)
        checkpoint.enable_circular_buffer = data.get('enable_circular_buffer', True)
        return checkpoint

class MongoCheckpoint(BaseCheckpointSaver):
    def __init__(self,
                 max_history_size: int = 100,
                 max_task_queue_size: int = 50,
                 enable_circular_buffer: bool = True):
        super().__init__()
        self.collection = None
        self.max_history_size = max_history_size
        self.max_task_queue_size = max_task_queue_size
        self.enable_circular_buffer = enable_circular_buffer

    async def _ensure_collection(self):
        """Ensure the collection is available"""
        if self.collection is None:
            if not db_client.is_connected():
                await db_client.connect()
            self.collection = await db_client.get_collection("checkpoints")

    @property
    def is_async(self) -> bool:
        return True

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        
        checkpoint_doc = await self.collection.find_one({"thread_id": thread_id})
        
        if checkpoint_doc:
            checkpoint_data = pickle.loads(checkpoint_doc["checkpoint"])

            if not isinstance(checkpoint_data, DequeCheckpoint):
                checkpoint_data = DequeCheckpoint(
                    checkpoint_data,
                    max_history_size=self.max_history_size,
                    max_task_queue_size=self.max_task_queue_size,
                    enable_circular_buffer=self.enable_circular_buffer
                )

            return CheckpointTuple(
                config, 
                checkpoint_data, 
                pickle.loads(checkpoint_doc.get("parent_checkpoint")) if checkpoint_doc.get("parent_checkpoint") else None,
            )
        return None
    
    async def alist(self, config: RunnableConfig) -> AsyncGenerator[CheckpointTuple, None]:
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]
        
        # Use async iterator directly
        async for doc in self.collection.find({"thread_id": thread_id}):
            # Create a temporary config for each document
            temp_config = config.copy()
            temp_config["configurable"] = config["configurable"].copy()
            temp_config["configurable"]["thread_id"] = doc.get("thread_id")

            checkpoint_data = pickle.loads(doc["checkpoint"])

            # Wrap in DequeCheckpoint if it's not already
            if not isinstance(checkpoint_data, DequeCheckpoint):
                checkpoint_data = DequeCheckpoint(
                    checkpoint_data,
                    max_history_size=self.max_history_size,
                    max_task_queue_size=self.max_task_queue_size,
                    enable_circular_buffer=self.enable_circular_buffer
                )
            
            yield CheckpointTuple(
                temp_config,
                checkpoint_data,
                pickle.loads(doc.get("parent_checkpoint")) if doc.get("parent_checkpoint") else None,
            )

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint,  
                   parent_checkpoint: Optional[Checkpoint] = None, 
                   metadata: Optional[Dict[str, Any]] = None) -> RunnableConfig:
        """
        Required method for LangGraph checkpoint system.
        This method is called by LangGraph to save checkpoints.
        """
        await self._ensure_collection()
        thread_id = config["configurable"]["thread_id"]

        # Wrap checkpoint in DequeCheckpoint if it's not already
        if not isinstance(checkpoint, DequeCheckpoint):
            checkpoint = DequeCheckpoint(
                checkpoint,
                max_history_size=self.max_history_size,
                max_task_queue_size=self.max_task_queue_size,
                enable_circular_buffer=self.enable_circular_buffer
            )

        # Extract timestamp from DequeCheckpoint
        timestamp = checkpoint.timestamp

        update_data = {
            "thread_id": thread_id,
            "checkpoint": pickle.dumps(checkpoint),
            "timestamp": timestamp,
            "checkpoint_id": checkpoint.checkpoint_id,
            "state_summary": checkpoint.get_state_summary(),
        }

        # Add parent checkpoint if provided
        if parent_checkpoint:
            update_data["parent_checkpoint"] = pickle.dumps(parent_checkpoint)
            
        # Add metadata if provided
        if metadata:
            update_data["metadata"] = metadata
        
        await self.collection.update_one(
            {"thread_id": thread_id},
            {
                "$set": update_data,
            },
            upsert=True,
        )
        return config

    async def aput_writes(self, config: RunnableConfig, checkpoint: Checkpoint, 
                         parent_checkpoint: Optional[Checkpoint] = None, 
                         metadata: Optional[Dict[str, Any]] = None) -> List[RunnableConfig]:
        """
        Required method for LangGraph checkpoint system.
        This method is called by LangGraph to save checkpoints.
        """
        await self.aput(config, checkpoint, parent_checkpoint, metadata)
        return [config]


    # Enhanced methods for deque-based functionality
    
    async def get_checkpoint_summary(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of the checkpoint state"""
        await self._ensure_collection()
        
        checkpoint_doc = await self.collection.find_one({"thread_id": thread_id})
        if checkpoint_doc and "state_summary" in checkpoint_doc:
            return checkpoint_doc["state_summary"]
        return None
    
    async def get_recent_checkpoints(self, thread_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent checkpoints for a thread"""
        await self._ensure_collection()
        
        cursor = self.collection.find(
            {"thread_id": thread_id}
        ).sort("timestamp", -1).limit(limit)
        
        checkpoints = []
        async for doc in cursor:
            checkpoints.append({
                "checkpoint_id": doc.get("checkpoint_id"),
                "timestamp": doc.get("timestamp"),
                "state_summary": doc.get("state_summary", {})
            })
        
        return checkpoints
    
    async def cleanup_old_checkpoints(self, thread_id: str, keep_last: int = 5):
        """Clean up old checkpoints, keeping only the most recent ones"""
        await self._ensure_collection()

        # Get all checkpoints for the thread, sorted by timestamp
        cursor = self.collection.find(
            {"thread_id": thread_id}
        ).sort("timestamp", -1)
        
        checkpoint_ids = []
        async for doc in cursor:
            checkpoint_ids.append(doc["_id"])
        
        # Keep only the most recent checkpoints
        if len(checkpoint_ids) > keep_last:
            checkpoints_to_delete = checkpoint_ids[keep_last:]
            await self.collection.delete_many({"_id": {"$in": checkpoints_to_delete}})

    async def get_thread_metrics(self, thread_id: str) -> Dict[str, Any]:
        """Get metrics for a specific thread"""
        await self._ensure_collection()
        
        checkpoint_doc = await self.collection.find_one({"thread_id": thread_id})
        if not checkpoint_doc:
            return {}
        
        summary = checkpoint_doc.get("state_summary", {})
        
        metrics = {
            "thread_id": thread_id,
            "last_activity": checkpoint_doc.get("timestamp"),
            "total_actions": summary.get("action_history_count", 0),
            "total_tasks": summary.get("total_tasks", 0),
            "pending_tasks": summary.get("pending_tasks", 0),
            "completed_tasks": summary.get("completed_tasks", 0),
            "child_results": summary.get("child_results_count", 0),
            "has_final_result": summary.get("final_result", False)
        }
        
        return metrics