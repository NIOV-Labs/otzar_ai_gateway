# app/workers/agent_worker.py
"""
Kafka Agent Worker Service

Handles task execution by consuming tasks from Kafka, executing them with
appropriate agents, and publishing results back to Kafka.
"""

import sys
import asyncio
import json
import logging
import signal
import time
import ssl
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError, ConsumerStoppedError

from app.core.config import settings
from app.agents.child_agents.research_agent import ResearchAgent
from app.agents.child_agents.translator_agent import TranslatorAgent

logging.basicConfig(
    level=logging.INFO,
    stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
)
logger = logging.getLogger(__name__)


class AgentWorkerError(Exception):
    """Custom exception for agent worker errors"""
    pass


class KafkaAgentWorker:
    """
    Kafka-based agent worker that consumes tasks and executes them
    """
    
    def __init__(self, worker_id: Optional[str] = None):
        self.worker_id = worker_id or f"worker-{int(time.time())}"
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.available_agents: Dict[str, Any] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._tasks_processed = 0
        self._tasks_failed = 0
        self._start_time = None

    async def initialize(self):
        """Initialize the worker with agents and Kafka connections"""
        try:
            logger.info(f"🔧 Initializing Kafka Agent Worker: {self.worker_id}")
            
            # Initialize agents
            await self._initialize_agents()
            
            # Setup Kafka connections
            await self._setup_kafka_consumer()
            await self._setup_kafka_producer()
            
            self._start_time = datetime.now(timezone.utc)
            logger.info(f"✅ Worker {self.worker_id} initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize worker {self.worker_id}: {e}")
            raise AgentWorkerError(f"Worker initialization failed: {e}")

    async def _initialize_agents(self):
        """Initialize available agents"""
        try:
            # Create agent instances
            agents = {
                "ResearchAgent": ResearchAgent(),
                "TranslatorAgent": TranslatorAgent(),
            }
            
            # Filter enabled agents (you could add config here)
            self.available_agents = {}
            for name, agent in agents.items():
                try:
                    # Validate agent has required methods
                    if hasattr(agent, 'execute_task'):
                        self.available_agents[name] = agent
                        logger.info(f"✅ Loaded agent: {name}")
                    else:
                        logger.warning(f"⚠️ Agent {name} missing execute_task method")
                except Exception as e:
                    logger.error(f"❌ Failed to load agent {name}: {e}")
            
            if not self.available_agents:
                raise AgentWorkerError("No valid agents loaded")
                
            logger.info(f"📋 Worker capable of running: {list(self.available_agents.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize agents: {e}")
            raise

    async def _setup_kafka_consumer(self):
        """Setup Kafka consumer for task consumption"""

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
                "agent-tasks",
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
                ssl_context=ssl_context,
                auto_offset_reset="latest",
                group_id="agent-worker-group",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=3000,
                max_poll_records=10,  # Process in small batches
            )
            
            await self.consumer.start()
            logger.info(f"📡 Kafka consumer started for worker {self.worker_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup Kafka consumer: {e}")
            raise

    async def _setup_kafka_producer(self):
        """Setup Kafka producer for result publishing"""

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
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
                ssl_context=ssl_context,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type="gzip",
                max_batch_size=16384,
                linger_ms=10,  # Small delay for batching
                retry_backoff_ms=100,
                request_timeout_ms=30000,
            )
            
            await self.producer.start()
            logger.info(f"📤 Kafka producer started for worker {self.worker_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup Kafka producer: {e}")
            raise

    async def _process_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Process a single task
        
        Args:
            task_data: Task data from Kafka message
            
        Returns:
            bool: True if processed successfully, False otherwise
        """
        task_id = task_data.get('task_id', 'unknown')
        agent_name = task_data.get('agent_name')
        conversation_id = task_data.get('conversation_id')
        
        try:
            # Check if task was already processed
            if await self.is_task_already_processed(task_id):
                logger.info(f"🔄 Task {task_id} already processed, skipping")
                return True
            
            # Validate task data
            if not self._validate_task_data(task_data):
                await self._send_error_result(task_data, "Invalid task data")
                return False
            
            # Check if we can handle this agent
            if agent_name not in self.available_agents:
                logger.warning(f"🚫 Ignoring task {task_id} for unknown agent '{agent_name}'")
                return True  # Not an error, just not our responsibility
            
            logger.info(f"🔄 Processing task {task_id} for agent '{agent_name}'")
            
            # Get the agent
            agent = self.available_agents[agent_name]
            
            # Execute the task
            start_time = time.time()
            
            # Check if agent supports async execution
            if hasattr(agent, 'aexecute_task'):
                result = await agent.aexecute_task(task_data)
            else:
                # Fallback to sync execution in thread pool
                result = await asyncio.get_event_loop().run_in_executor(
                    None, agent.execute_task, task_data
                )
            
            execution_time = time.time() - start_time

            # Mark task as processed
            await self._mark_task_processed(task_id)
            
            # Send success result
            await self._send_success_result(task_data, result, execution_time)
            
            self._tasks_processed += 1
            logger.info(f"✅ Task {task_id} completed in {execution_time:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"❌ Task {task_id} failed: {e}", exc_info=True)
            await self._send_error_result(task_data, str(e))
            self._tasks_failed += 1
            return False

    async def is_task_already_processed(self, task_id: str) -> bool:
        """Check if task was already processed by checking database"""
        try:
            from app.core.db_client import db_client
            if not db_client.is_connected():
                await db_client.connect()
            
            tasks_collection = await db_client.get_collection("tasks")
            
            # Check if task exists and has a result
            task_doc = await tasks_collection.find_one({
                "task_id": task_id,
                "status": {"$in": ["COMPLETED", "FAILED"]}
            })

            return task_doc is not None
        
        except Exception as e:
            logger.error(f"❌ Failed to check status of task {task_id}: {e}")
            return False

    async def _mark_task_processed(self, task_id: str):
        """Mark task as processed in database"""
        try:
            from app.core.db_client import db_client
            if not db_client.is_connected():
                await db_client.connect()
            
            tasks_collection = await db_client.get_collection("tasks")
            
            # Update task status to mark as processed
            await tasks_collection.update_one(
                {"task_id": task_id},
                {
                    "$set": {
                        "processed_at": datetime.now(timezone.utc),
                        "processed_by": self.worker_id
                    }
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"❌ Error marking task as processed: {e}")

    def _validate_task_data(self, task_data: Dict[str, Any]) -> bool:
        """Validate required task data fields"""
        required_fields = ['task_id', 'agent_name', 'conversation_id']
        
        for field in required_fields:
            if field not in task_data:
                logger.error(f"❌ Missing required field: {field}")
                return False
        
        return True

    async def _send_success_result(self, task_data: Dict[str, Any], result: Any, execution_time: float):
        """Send successful task result to Kafka"""
        try:
            result_event = {
                "task_id": task_data['task_id'],
                "conversation_id": task_data['conversation_id'],
                "status": "completed",
                "result": result,
                "worker_id": self.worker_id,
                "execution_time": execution_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.producer.send('agent-results', value=result_event)
            await self.producer.flush()
            
            logger.info(f"📤 Sent success result for task {task_data['task_id']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send success result: {e}")
            raise

    async def _send_error_result(self, task_data: Dict[str, Any], error_message: str):
        """Send error result to Kafka"""
        try:
            error_event = {
                "task_id": task_data.get('task_id', 'unknown'),
                "conversation_id": task_data.get('conversation_id', 'unknown'),
                "status": "failed",
                "error": error_message,
                "worker_id": self.worker_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.producer.send('agent-results', value=error_event)
            await self.producer.flush()
            
            logger.info(f"📤 Sent error result for task {task_data.get('task_id', 'unknown')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send error result: {e}")

    async def _consume_messages(self):
        """Main message consumption loop"""
        try:
            logger.info(f"🚀 Starting message consumption for worker {self.worker_id}")
            
            async for message in self.consumer:
                if self._shutdown_event.is_set():
                    logger.info("🛑 Shutdown signal received, stopping consumption")
                    break
                
                try:
                    task_data = message.value
                    await self._process_task(task_data)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}", exc_info=True)
                    # Continue processing other messages
                    
        except ConsumerStoppedError:
            logger.info("📡 Consumer stopped")
        except Exception as e:
            logger.error(f"❌ Error in message consumption loop: {e}")
            raise

    async def start(self):
        """Start the worker"""
        if self._running:
            logger.warning("Worker is already running")
            return
            
        try:
            await self.initialize()
            self._running = True
            
            logger.info(f"🚀 Starting Kafka Agent Worker: {self.worker_id}")
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Start consuming messages
            await self._consume_messages()
            
        except KeyboardInterrupt:
            logger.info("🛑 Received shutdown signal")
        except Exception as e:
            logger.error(f"❌ Worker error: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the worker gracefully"""
        if not self._running:
            return
            
        self._running = False
        self._shutdown_event.set()
        
        logger.info(f"🛑 Stopping Kafka Agent Worker: {self.worker_id}")
        
        try:
            # Stop Kafka connections
            if self.consumer:
                await self.consumer.stop()
                logger.info("📡 Kafka consumer stopped")
                
            if self.producer:
                await self.producer.stop()
                logger.info("📤 Kafka producer stopped")
                
            # Log final statistics
            uptime = datetime.now(timezone.utc) - self._start_time if self._start_time else None
            logger.info(f"📊 Worker {self.worker_id} statistics:")
            logger.info(f"   Tasks processed: {self._tasks_processed}")
            logger.info(f"   Tasks failed: {self._tasks_failed}")
            logger.info(f"   Uptime: {uptime}")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            # logger.info(f"Received signal {signum}, initiating shutdown...")
            print(f"Received signal {signum}, initiating shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            uptime = datetime.now(timezone.utc) - self._start_time if self._start_time else None
            
            return {
                "status": "healthy" if self._running else "stopped",
                "worker_id": self.worker_id,
                "agents_loaded": list(self.available_agents.keys()),
                "tasks_processed": self._tasks_processed,
                "tasks_failed": self._tasks_failed,
                "uptime_seconds": uptime.total_seconds() if uptime else 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    @asynccontextmanager
    async def lifespan(self):
        """Context manager for worker lifecycle"""
        try:
            await self.initialize()
            yield self
        finally:
            await self.stop()


class WorkerPool:
    """Manages multiple worker instances for horizontal scaling"""
    
    def __init__(self, num_workers: int = 1):
        self.num_workers = num_workers
        self.workers: list[KafkaAgentWorker] = []
        self._running = False

    async def start(self):
        """Start all workers in the pool"""
        try:
            logger.info(f"🚀 Starting worker pool with {self.num_workers} workers")
            
            # Create and start workers
            tasks = []
            for i in range(self.num_workers):
                worker = KafkaAgentWorker(worker_id=f"worker-pool-{i}")
                self.workers.append(worker)
                tasks.append(asyncio.create_task(worker.start()))
            
            self._running = True
            
            # Wait for all workers to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"❌ Worker pool error: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop all workers in the pool"""
        if not self._running:
            return
            
        self._running = False
        logger.info("🛑 Stopping worker pool")
        
        # Stop all workers
        stop_tasks = []
        for worker in self.workers:
            stop_tasks.append(asyncio.create_task(worker.stop()))
        
        await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        logger.info("✅ Worker pool stopped")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for the entire pool"""
        worker_statuses = []
        
        for worker in self.workers:
            status = await worker.health_check()
            worker_statuses.append(status)
        
        healthy_workers = sum(1 for status in worker_statuses if status["status"] == "healthy")
        
        return {
            "status": "healthy" if healthy_workers > 0 else "unhealthy",
            "total_workers": len(self.workers),
            "healthy_workers": healthy_workers,
            "worker_statuses": worker_statuses,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Factory functions
def create_worker(worker_id: Optional[str] = None) -> KafkaAgentWorker:
    """Create a new worker instance"""
    return KafkaAgentWorker(worker_id=worker_id)


def create_worker_pool(num_workers: int = 1) -> WorkerPool:
    """Create a new worker pool"""
    return WorkerPool(num_workers=num_workers)


# Main entry point
async def main():
    """Main entry point for running a single worker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    worker = create_worker()
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Worker interrupted by user")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())