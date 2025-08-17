# app/services/result_ingestor.py
"""
Result Ingestor Service

Handles incoming agent results from Kafka and updates both task status
and LangGraph checkpoints accordingly.
"""

from datetime import datetime, timezone
import ssl
import sys
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from app.core.config import settings
from app.core.db_client import db_client
from app.state.mongo_checkpoint import MongoCheckpoint, DequeCheckpoint
from app.services.agent_service import get_agent_service

logging.basicConfig(
    level=logging.INFO,
    stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
)
logger = logging.getLogger(__name__)


class ResultIngestorError(Exception):
    """Custom exception for result ingestor errors"""
    pass


class ResultIngestorService:
    """Service to consume agent results from Kafka and update database/checkpoints"""
    
    def __init__(self):
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.checkpoint_saver: Optional[MongoCheckpoint] = None
        self.tasks_collection = None
        self.ai_responses_collection = None
        self._running = False

    async def initialize(self):
        """Initialize the service components"""
        try:
            # Initialize database connection
            if not db_client.is_connected():
                await db_client.connect()
            
            # Get collections
            self.tasks_collection = await db_client.get_collection("tasks")
            self.ai_responses_collection = await db_client.get_collection("ai_responses")
            
            # Initialize checkpoint saver
            self.checkpoint_saver = MongoCheckpoint()
            
            # Initialize Kafka consumer
            await self._setup_kafka_consumer()
            
            logger.info("✅ Result Ingestor Service initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Result Ingestor Service: {e}")
            raise ResultIngestorError(f"Initialization failed: {e}")

    async def _setup_kafka_consumer(self):
        """Setup and configure Kafka consumer"""

        # SSL context for Aiven Kafka
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_REQUIRED

        # Load certificates if using client certificates (recommended for production)
        if hasattr(settings, 'KAFKA_SSL_CAFILE') and settings.KAFKA_SSL_CAFILE:
            ssl_context.load_verify_locations(settings.KAFKA_SSL_CAFILE)
        
        if (hasattr(settings, 'KAFKA_SSL_CERTFILE') and settings.KAFKA_SSL_CERTFILE and 
            hasattr(settings, 'KAFKA_SSL_KEYFILE') and settings.KAFKA_SSL_KEYFILE):
            ssl_context.load_cert_chain(settings.KAFKA_SSL_CERTFILE, settings.KAFKA_SSL_KEYFILE)

        try:
            self.consumer = AIOKafkaConsumer(
                "agent-results",
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
                ssl_context=ssl_context,
                auto_offset_reset="earliest",
                group_id="result-ingestor-group",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
            )
            
            await self.consumer.start()
            logger.info("📡 Kafka consumer started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup Kafka consumer: {e}")
            raise

    async def _process_result_event(self, result_event: Dict[str, Any]) -> bool:
        """
        Process a single result event
        
        Args:
            result_event: The result event data from Kafka
            
        Returns:
            bool: True if processed successfully, False otherwise
        """
        try:
            conversation_id = result_event.get('conversation_id')
            
            if not conversation_id:
                logger.warning(f"No conversation_id found in result event: {result_event}")
                return False

            logger.info(f"🔄 Processing result for conversation {conversation_id}")
            
            # Update task status
            await self._update_task_status(conversation_id, result_event)

            # Store AI response
            await self._store_ai_response(conversation_id, result_event)
            
            # Update LangGraph checkpoint
            await self._update_checkpoint(conversation_id, result_event)
            
            logger.info(f"✅ Successfully processed result for conversation {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing result event: {e}", exc_info=True)
            return False

    async def _update_task_status(self, conversation_id: str, result_event: Dict[str, Any]):
        """Update the task status in the database"""
        try:
            status = "COMPLETED" if result_event.get('status') == 'completed' else "FAILED"
            
            update_data = {
                "status": status,
                "result": result_event.get('result'),
                "error": result_event.get('error'),
                "updated_at": result_event.get('timestamp')  # Add timestamp if available
            }
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            result = await self.tasks_collection.update_one(
                {"conversation_id": conversation_id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                logger.warning(f"No task found with conversation_id: {conversation_id}")
            else:
                logger.info(f"📝 Updated task status to {status} for conversation {conversation_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to update task status for {conversation_id}: {e}")
            raise

    async def _store_ai_response(self, conversation_id: str, result_event: Dict[str, Any]):
        """Store AI response in the ai_responses collection"""
        try:
            # Extract relevant data from result event
            ai_response_document = {
                "conversation_id": conversation_id,
                "task_id": result_event.get('task_id'),
                "agent_name": result_event.get('agent_name', 'unknown'),
                "status": result_event.get('status'),
                "ai_response": result_event.get('result'),
                "error": result_event.get('error'),
                "worker_id": result_event.get('worker_id'),
                "execution_time": result_event.get('execution_time'),
                "timestamp": result_event.get('timestamp'),
                "created_at": datetime.now(timezone.utc),
                "metadata": {
                    "source": "child_agent",
                    "event_type": "agent_result"
                }
            }
            
            # Remove None values
            ai_response_document = {k: v for k, v in ai_response_document.items() if v is not None}
            
            # Insert the AI response
            result = await self.ai_responses_collection.insert_one(ai_response_document)
            
            logger.info(f"�� Stored AI response for conversation {conversation_id}, task {result_event.get('task_id')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to store AI response for {conversation_id}: {e}")
            raise

    async def _update_checkpoint(self, conversation_id: str, result_event: Dict[str, Any]):
        """Update the LangGraph checkpoint"""
        try:
            config = {"configurable": {"thread_id": conversation_id}}
            checkpoint_tuple = await self.checkpoint_saver.aget_tuple(config)
            
            if not checkpoint_tuple:
                logger.warning(f"No checkpoint found for conversation {conversation_id}")
                return
                
            checkpoint = checkpoint_tuple.checkpoint
            
            # Update the checkpoint state
            if self._update_checkpoint_state(checkpoint, result_event):
                await self.checkpoint_saver.aput(config, checkpoint)
                logger.info(f"📋 Updated LangGraph checkpoint for conversation {conversation_id}")

                # Remove the workflow continuation call - LangGraph handles this automatically
                # await self._trigger_workflow_continuation(conversation_id, config)
                # Trigger workflow continuation now that state changed
                try:
                    agent_service = await get_agent_service()
                    await agent_service.continue_workflow(conversation_id)
                    logger.info(f"▶️ Continued workflow for conversation {conversation_id}")
                except Exception as e:
                    logger.warning(f"Could not continuw workflow automatically for {conversation_id}")
            else:
                logger.warning(f"Failed to update checkpoint state for {conversation_id}")
                
        except Exception as e:
            logger.error(f"❌ Failed to update checkpoint for {conversation_id}: {e}")
            raise

    # TODO: Remove this function - LangGraph handles this automatically
    # async def _trigger_workflow_continuation(self, conversation_id: str, config: Dict[str, Any]):
    #     """Trigger the workflow to continue after result is received"""
    #     try:
    #         # Get the agent service instance (you'll need to inject this)
    #         from app.services.agent_service import get_agent_service
    #         agent_service = await get_agent_service()
            
    #         # Continue the workflow
    #         await agent_service.continue_workflow(conversation_id, config)
    #         logger.info(f"�� Triggered workflow continuation for {conversation_id}")
            
    #     except Exception as e:
    #         logger.error(f"❌ Failed to trigger workflow continuation: {e}")

    def _update_checkpoint_state(self, checkpoint: Dict[str, Any], result_event: Dict[str, Any]) -> bool:
        """
        Update the checkpoint state with result data
        
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            # # Check if decomposed_tasks exists in checkpoint
            # if "channel_values" not in checkpoint or "decomposed_tasks" not in checkpoint["channel_values"]:
            #     logger.warning("No decomposed_tasks found in checkpoint")
            #     return False
                
            # decomposed_tasks = checkpoint["channel_values"]["decomposed_tasks"]
            
            # if not decomposed_tasks:
            #     logger.warning("Empty decomposed_tasks in checkpoint")
            #     return False

            # Unwrap DequeCheckpoint to raw state dict when needed
            state = checkpoint.data if isinstance(checkpoint, DequeCheckpoint) else checkpoint
            if not isinstance(state, dict):
                logger.warning(f"Unexpected checkpoint type: {type(checkpoint)}")
                return False

            # Prefer channel_values if present; otherwise operate directly on state
            channel_values = state.get("channel_values", state)

            # Validate structure
            if "decomposed_tasks" not in channel_values:
                logger.warning("No decomposed tasks found in checkpoint")
                return False

            decomposed_tasks = channel_values["decomposed_tasks"]
            if not decomposed_tasks:
                logger.warning("Empty decomposed_tasks in checkpoint")
                return False
                
            # Update the last task with the result
            last_task = decomposed_tasks[-1]
            task_id = result_event.get('task_id') or last_task.get("task_id")
            
            # Find and update the specific task
            task_updated = False
            for task in decomposed_tasks:
                if task.get("task_id") == task_id:
                    task["status"] = "COMPLETED" if result_event.get('status') == 'completed' else "FAILED"
                    task["result"] = result_event.get('result')
                    if result_event.get('error'):
                        task["error"] = result_event.get('error')
                    task_updated = True
                    logger.info(f"✅ Updated task {task_id} with result: {result_event.get('result')} in checkpoint")
                    break
            
            if not task_updated:
                logger.warning(f"Task with ID {task_id} not found in decomposed_tasks")
                return False
            
            # Check if all tasks are completed and update next_agent
            pending_tasks = [t for t in decomposed_tasks if t.get("status") == "pending"]
            if not pending_tasks:
                # All tasks are completed, set next_agent to process_results
                if "next_agent" not in channel_values:
                    channel_values["next_agent"] = "process_results"
                    logger.info(f"🔄 All tasks are completed, setting next_agent to process_results")
                # else:
                #     logger.info(f"✅ All tasks are completed, next_agent is already set to {checkpoint['channel_values']['next_agent']}")

            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating checkpoint state: {e}")
            return False

    async def store_final_synthesized_result(self, conversation_id: str, final_result: str, metadata: Optional[Dict[str, Any]] = None):
        """Store the final synthesized result from the master agent"""
        try:
            final_response_document = {
                "conversation_id": conversation_id,
                "task_id": None,  # This is the final result, not a specific task
                "agent_name": "MasterAgent",
                "status": "completed",
                "ai_response": final_result,
                "error": None,
                "worker_id": "master_agent",
                "execution_time": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc),
                "metadata": {
                    "source": "master_agent",
                    "event_type": "final_synthesis",
                    "is_final_result": True,
                    **(metadata or {})
                }
            }
            
            # Insert the final AI response
            result = await self.ai_responses_collection.insert_one(final_response_document)
            
            logger.info(f"💾 Stored final synthesized AI response for conversation {conversation_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to store final AI response for {conversation_id}: {e}")
            raise

    async def _consume_messages(self):
        """Main message consumption loop"""
        try:
            async for message in self.consumer:
                try:
                    result_event = message.value
                    success = await self._process_result_event(result_event)
                    
                    if not success:
                        logger.error(f"Failed to process message: {result_event}")
                        # In production, you might want to send to dead letter queue
                        
                except Exception as e:
                    logger.error(f"❌ Error processing Kafka message: {e}", exc_info=True)
                    # Continue processing other messages
                    
        except Exception as e:
            logger.error(f"❌ Error in message consumption loop: {e}")
            raise

    async def start(self):
        """Start the result ingestor service"""
        if self._running:
            logger.warning("Service is already running")
            return
            
        try:
            await self.initialize()
            self._running = True
            
            logger.info("🚀 Starting Result Ingestor Service...")
            await self._consume_messages()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal")
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the result ingestor service"""
        if not self._running:
            return
            
        self._running = False
        logger.info("🛑 Stopping Result Ingestor Service...")
        
        try:
            if self.consumer:
                await self.consumer.stop()
                logger.info("📡 Kafka consumer stopped")
                
            await db_client.close()
            logger.info("🔌 Database connection closed")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

    @asynccontextmanager
    async def lifespan(self):
        """Context manager for service lifecycle"""
        try:
            await self.initialize()
            yield self
        finally:
            await self.stop()


# Factory function for creating service instance
def create_result_ingestor_service() -> ResultIngestorService:
    """Create and return a new ResultIngestorService instance"""
    return ResultIngestorService()


# Main entry point for running as standalone service
async def main():
    """Main entry point for the service"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    service = create_result_ingestor_service()
    
    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("🛑 Service interrupted by user")
    except Exception as e:
        logger.error(f"❌ Service failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())