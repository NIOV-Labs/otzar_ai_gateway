# app/services/agent_service.py
"""
Service layer for initializing and running the agent workflow.

This service manages the complete agent workflow lifecycle including:
- Task creation and management
- Agent workflow execution
- State management and checkpointing
- Streaming capabilities
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.state.graph_state import MasterAgentState, AgentTask
from app.agents.child_agents.research_agent import ResearchAgent
from app.agents.child_agents.translator_agent import TranslatorAgent
from app.agents.master_agent import MasterAgent
from app.state.mongo_checkpoint import MongoCheckpoint
from app.core.db_client import db_client

logger = logging.getLogger(__name__)


class AgentServiceError(Exception):
    """Custom exception for agent service errors"""
    pass


class AgentWorkflowService:
    """Service for managing agent workflows and task execution"""
    
    def __init__(self):
        self.tasks_collection = None
        self.checkpoint_saver: Optional[MongoCheckpoint] = None
        self.agent_registry: Dict[str, Any] = {}
        self.master_agent: Optional[MasterAgent] = None
        self.app_graph: Optional[CompiledStateGraph] = None
        self._initialized = False

    async def initialize(self):
        """Initialize the service with all dependencies"""
        if self._initialized:
            return
            
        try:
            logger.info("🔧 Initializing Agent Workflow Service...")
            
            # Initialize database connection
            if not db_client.is_connected():
                await db_client.connect()
            
            # Get collections
            self.tasks_collection = await db_client.get_collection("tasks")
            
            # Initialize checkpoint saver
            self.checkpoint_saver = MongoCheckpoint()
            
            # Initialize agents
            await self._initialize_agents()
            
            # Build workflow graph
            await self._build_workflow_graph()
            
            self._initialized = True
            logger.info("✅ Agent Workflow Service initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Agent Workflow Service: {e}")
            raise AgentServiceError(f"Initialization failed: {e}")

    async def _initialize_agents(self):
        """Initialize all agents and build registry"""
        try:
            # 1. Instantiate Child Agents
            research_agent = ResearchAgent()
            translator_agent = TranslatorAgent()
            
            # 2. Create the Agent Registry
            self.agent_registry = {
                research_agent.get_name(): research_agent,
                translator_agent.get_name(): translator_agent
            }
            
            # 3. Instantiate the Master Agent with the registry
            self.master_agent = MasterAgent(self.agent_registry)

            # Initialize the master agent with the registry
            await self.master_agent.initialize()
            
            logger.info(f"📋 Initialized {len(self.agent_registry)} agents")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize agents: {e}")
            raise

    async def _build_workflow_graph(self):
        """Build and compile the LangGraph workflow"""
        try:
            # Define the workflow graph
            workflow = StateGraph(MasterAgentState)
            
            # Add the nodes to the graph
            workflow.add_node("parse_user_request", self.master_agent.parse_user_request)
            workflow.add_node("route_to_agent", self.master_agent.route_to_agent)
            workflow.add_node("delegate_task", self.master_agent.delegate_task)
            workflow.add_node("wait_for_results", self.master_agent.wait_for_results)
            workflow.add_node("process_results", self.master_agent.process_results)
            workflow.add_node("synthesize_final_results", self.master_agent.synthesize_final_results)
            
            # Set the entry point of the graph
            workflow.set_entry_point("parse_user_request")
            
            # Add edges to define the flow
            workflow.add_edge("parse_user_request", "route_to_agent")
            workflow.add_edge("route_to_agent", "delegate_task")
            workflow.add_edge("delegate_task", "wait_for_results")

            # Use conditional routing for the rest of the flow
            workflow.add_conditional_edges(
                "wait_for_results",
                self.master_agent.router,
                {
                    # "wait_for_results": "wait_for_results", # Self-loop for waiting
                    "wait_for_results": END, # Pause run instead of self-logging
                    "process_results": "process_results",
                    "end": END
                }
            )

            workflow.add_conditional_edges(
                "process_results",
                self.master_agent.router,
                {
                    "synthesize_final_results": "synthesize_final_results",
                    "end": END
                }
            )  

            workflow.add_conditional_edges(
                "synthesize_final_results",
                self.master_agent.router,
                {
                    "end": END
                }
            )

            # workflow.add_edge("wait_for_results", "wait_for_results")  # Self-loop for waiting
            # workflow.add_edge("wait_for_results", "process_results")
            # workflow.add_edge("process_results", "synthesize_final_results")
            # workflow.add_edge("synthesize_final_results", END)
            
            
            # Compile the graph into a runnable application
            self.app_graph = workflow.compile(checkpointer=self.checkpoint_saver)
            
            logger.info("🔗 Workflow graph compiled successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to build workflow graph: {e}")
            raise

    async def create_new_task(self, user_input: str, context_id: Optional[str] = None) -> str:
        """
        Creates a new conversation ID and sets its initial state.
        
        Args:
            user_input: The user's request/input
            context_id: Optional context identifier
            
        Returns:
            str: The conversation ID for the new task
        """
        await self._ensure_initialized()
        
        try:
            conversation_id = str(uuid.uuid4())
            
            task_document = {
                "conversation_id": conversation_id,
                "status": "PENDING",
                "user_input": user_input,
                "context_id": context_id,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "result": None,
                "error": None
            }
            
            await self.tasks_collection.insert_one(task_document)
            
            logger.info(f"📝 Created new task: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create new task: {e}")
            raise AgentServiceError(f"Task creation failed: {e}")

    async def get_task_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the status of a task.
        
        Args:
            conversation_id: The conversation/task ID
            
        Returns:
            dict: Task status information or None if not found
        """
        await self._ensure_initialized()
        
        try:
            task = await self.tasks_collection.find_one({"conversation_id": conversation_id})
            
            if task:
                # Remove MongoDB's _id field for clean response
                task.pop('_id', None)

                if 'created_at' in task and task['created_at']:
                    task['created_at'] = task['created_at'].isoformat()

                if 'updated_at' in task and task['updated_at']:
                    task['updated_at'] = task['updated_at'].isoformat()

                logger.debug(f"📊 Retrieved task status: {conversation_id}")
            else:
                logger.warning(f"📊 Task not found: {conversation_id}")
                
            return task
            
        except Exception as e:
            logger.error(f"❌ Failed to get task status for {conversation_id}: {e}")
            raise AgentServiceError(f"Task status retrieval failed: {e}")

    async def start_agent_workflow(self, conversation_id: str, user_input: str, context_id: Optional[str] = None):
        """
        Execute the agent workflow for a given task.
        
        Args:
            conversation_id: The conversation/task ID
            user_input: The user's request
            context_id: Optional context identifier
        """
        await self._ensure_initialized()
        
        try:
            logger.info(f"🚀 Starting agent workflow: {conversation_id}")
            
            # Update task status to running
            await self._update_task_status(
                conversation_id, 
                status="RUNNING",
                extra_fields={"started_at": datetime.now(timezone.utc)}
            )
            
            # Set the initial state for the run
            initial_state = {
                "original_request": user_input,
                "context_id": context_id,
                "conversation_id": conversation_id,
                "retrieved_context": None,
                "parsed_instructions": None,
                "decomposed_tasks": [],
                "child_results": [],
                "action_history": [],
                "final_result": None,
                "next_agent": None
            }
            
            # Configuration for LangGraph state management
            config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": 50}
            
            # Execute the workflow
            await self.app_graph.ainvoke(initial_state, config=config)
            
            logger.info(f"✅ Agent workflow initiated: {conversation_id}")
            
        except Exception as e:
            logger.error(f"❌ Agent workflow failed for {conversation_id}: {e}")
            
            # Update task status to failed
            await self._update_task_status(
                conversation_id,
                status="FAILED",
                extra_fields={
                    "error": str(e),
                    "failed_at": datetime.now(timezone.utc)
                }
            )
            raise AgentServiceError(f"Workflow execution failed: {e}")

    async def stream_agent_workflow(self, user_input: str, agent_name: str = "ResearchAgent") -> AsyncGenerator[str, None]:
        """
        Stream the output of an agent workflow.
        
        Args:
            user_input: The user's request
            agent_name: Name of the agent to use for streaming
            
        Yields:
            str: Server-Sent Events formatted data chunks
        """
        await self._ensure_initialized()
        
        try:
            # Get the specified agent
            if agent_name not in self.agent_registry:
                raise AgentServiceError(f"Agent '{agent_name}' not found in registry")
                
            agent = self.agent_registry[agent_name]
            
            # Check if agent supports streaming
            if not hasattr(agent, 'stream_task'):
                raise AgentServiceError(f"Agent '{agent_name}' does not support streaming")
            
            logger.info(f"🌊 Starting streaming workflow with {agent_name}")
            
            # Create a transient task for streaming
            task = AgentTask(
                task_id=uuid.uuid4(),
                task="Streaming Task",
                instructions=user_input,
                agent_name=agent_name,
                status="RUNNING",
                dependencies=[],
                result=None
            )
            
            # Stream the agent output
            async for content_chunk in agent.stream_task(task):
                # Format as Server-Sent Events
                data_to_send = json.dumps({"token": content_chunk})
                yield f"data: {data_to_send}\n\n"
            
            # Send completion signal
            done_message = json.dumps({"token": "[DONE]"})
            yield f"data: {done_message}\n\n"
            
            logger.info(f"✅ Streaming workflow completed for {agent_name}")
            
        except Exception as e:
            logger.error(f"❌ Streaming workflow failed: {e}")
            error_message = json.dumps({"token": f"Error: {str(e)}"})
            yield f"data: {error_message}\n\n"

    async def get_ai_responses(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all AI responses for a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            List of AI response documents
        """
        await self._ensure_initialized()
        
        try:
            # Get the AI responses collection
            ai_responses_collection = await db_client.get_collection("ai_responses")
            
            # Find all responses for this conversation
            cursor = ai_responses_collection.find({"conversation_id": conversation_id})
            responses = await cursor.to_list(length=None)
            
            # Convert ObjectId to string for JSON serialization
            for response in responses:
                if '_id' in response:
                    response['_id'] = str(response['_id'])
                if 'created_at' in response and response['created_at']:
                    response['created_at'] = response['created_at'].isoformat()
            
            logger.info(f"�� Retrieved {len(responses)} AI responses for conversation {conversation_id}")
            return responses
            
        except Exception as e:
            logger.error(f"❌ Failed to get AI responses for {conversation_id}: {e}")
            raise AgentServiceError(f"AI responses retrieval failed: {e}")

    # TODO: Remove this function but check first - LangGraph handles this automatically
    async def continue_workflow(self, conversation_id: str) -> None:
        """
        Manually continue a workflow from a checkpoint.
        
        Args:
            conversation_id: The conversation ID
           
        """
        await self._ensure_initialized()
        try:
            logger.info(f"🔄 Manually continuing workflow for {conversation_id}")
            # logger.info(f"🔁 Continuing workflow: {conversation_id}")
            config = {"configurable": {"thread_id": conversation_id}, "recursion_limit": 50}
            
            # Get the current checkpoint
            checkpoint_tuple = await self.checkpoint_saver.aget_tuple(config)
            
            if not checkpoint_tuple:
                logger.warning(f"No checkpoint found for conversation {conversation_id} to continue")
                return
            
            # Continue the workflow from the checkpoint
            # async for chunk in self.app_graph.astream(
            #     checkpoint_tuple.checkpoint,
            #     config=config
            # ):
            #     # Process the chunk if needed
            #     logger.debug(f"Workflow chunk: {chunk}")

            # Unwrap DequeCheckpoint to get the raw state
            checkpoint = checkpoint_tuple.checkpoint
            if hasattr(checkpoint, 'data'):
                # It's a DequeCheckpoint, extract the data
                state = checkpoint.data
            else:
                # It's already a raw state dict
                state = checkpoint

            await self.app_graph.ainvoke(state, config=config)
            
            logger.info(f"✅ Workflow continued successfully for {conversation_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to continue workflow for {conversation_id}: {e}")
            raise AgentServiceError(f"Workflow continuation failed: {e}")
    

    async def list_tasks(self, limit: int = 50, skip: int = 0, status_filter: Optional[str] = None) -> list:
        """
        List tasks with optional filtering and pagination.
        
        Args:
            limit: Maximum number of tasks to return
            skip: Number of tasks to skip (for pagination)
            status_filter: Optional status to filter by
            
        Returns:
            list: List of task documents
        """
        await self._ensure_initialized()
        
        try:
            query = {}
            if status_filter:
                query["status"] = status_filter
            
            cursor = self.tasks_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
            tasks = []
            
            async for task in cursor:
                task.pop('_id', None)  # Remove MongoDB's _id field
                tasks.append(task)
            
            logger.info(f"📋 Retrieved {len(tasks)} tasks")
            return tasks
            
        except Exception as e:
            logger.error(f"❌ Failed to list tasks: {e}")
            raise AgentServiceError(f"Task listing failed: {e}")

    async def cancel_task(self, conversation_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            conversation_id: The conversation/task ID to cancel
            
        Returns:
            bool: True if cancelled successfully, False if not found or already completed
        """
        await self._ensure_initialized()
        
        try:
            # Check current status
            task = await self.get_task_status(conversation_id)
            
            if not task:
                logger.warning(f"🚫 Task not found for cancellation: {conversation_id}")
                return False
            
            if task["status"] in ["COMPLETED", "FAILED", "CANCELLED"]:
                logger.warning(f"🚫 Task already finished: {conversation_id} (status: {task['status']})")
                return False
            
            # Update status to cancelled
            await self._update_task_status(
                conversation_id,
                status="CANCELLED",
                extra_fields={"cancelled_at": datetime.now(timezone.utc)}
            )
            
            logger.info(f"🚫 Task cancelled: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel task {conversation_id}: {e}")
            raise AgentServiceError(f"Task cancellation failed: {e}")

    async def _update_task_status(self, conversation_id: str, status: str, extra_fields: Optional[Dict[str, Any]] = None):
        """Update task status with optional extra fields"""
        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc)
        }
        
        if extra_fields:
            update_data.update(extra_fields)
        
        await self.tasks_collection.update_one(
            {"conversation_id": conversation_id},
            {"$set": update_data}
        )

    async def _ensure_initialized(self):
        """Ensure the service is initialized"""
        if not self._initialized:
            await self.initialize()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the service.
        
        Returns:
            dict: Health status information
        """
        try:
            await self._ensure_initialized()
            
            # Check database connection
            db_healthy = await db_client.health_check()
            
            # Check if agents are available
            agents_healthy = len(self.agent_registry) > 0
            
            # Check if graph is compiled
            graph_healthy = self.app_graph is not None
            
            overall_healthy = db_healthy and agents_healthy and graph_healthy
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "database": "healthy" if db_healthy else "unhealthy",
                "agents": "healthy" if agents_healthy else "unhealthy",
                "graph": "healthy" if graph_healthy else "unhealthy",
                "agent_count": len(self.agent_registry),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def stop(self):
        """Stop the service and cleanup resources"""
        try:
            if self.master_agent:
                await self.master_agent.cleanup()
            if self.app_graph:
                # Cleanup graph resources if needed
                # TODO: Implement graph cleanup

                pass
                
            logger.info("✅ Agent Workflow Service stopped")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")


    @asynccontextmanager
    async def lifespan(self):
        """Context manager for service lifecycle"""
        try:
            await self.initialize()
            yield self
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        try:
            if db_client.is_connected():
                await db_client.close()
            logger.info("🧹 Agent service cleanup completed")
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")


# Singleton instance for the service
_agent_service: Optional[AgentWorkflowService] = None


async def get_agent_service() -> AgentWorkflowService:
    """
    Get or create the singleton agent service instance.
    
    Returns:
        AgentWorkflowService: The singleton service instance
    """
    global _agent_service
    
    if _agent_service is None:
        _agent_service = AgentWorkflowService()
        await _agent_service.initialize()
    
    return _agent_service


# Factory function for creating a new service instance
def create_agent_service() -> AgentWorkflowService:
    """Create and return a new AgentWorkflowService instance"""
    return AgentWorkflowService()


# Legacy compatibility functions (optional - for backward compatibility)
async def start_agent_workflow(conversation_id: str, user_input: str, context_id: Optional[str] = None):
    """Legacy function - use get_agent_service().start_agent_workflow() instead"""
    service = await get_agent_service()
    return await service.start_agent_workflow(conversation_id, user_input, context_id)


async def create_new_task(user_input: str, context_id: Optional[str] = None) -> str:
    """Legacy function - use get_agent_service().create_new_task() instead"""
    service = await get_agent_service()
    return await service.create_new_task(user_input, context_id)


async def get_task_status(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Legacy function - use get_agent_service().get_task_status() instead"""
    service = await get_agent_service()
    return await service.get_task_status(conversation_id)


async def stream_agent_workflow(user_input: str) -> AsyncGenerator[str, None]:
    """Legacy function - use get_agent_service().stream_agent_workflow() instead"""
    service = await get_agent_service()
    async for chunk in service.stream_agent_workflow(user_input):
        yield chunk