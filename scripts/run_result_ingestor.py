#!/usr/bin/env python3
"""
Service runner for the Result Ingestor Service

Usage:
    python run_result_ingestor.py
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.result_ingestor import create_result_ingestor_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('result_ingestor.log')
    ]
)

logger = logging.getLogger(__name__)


class ServiceRunner:
    """Runner for managing the Result Ingestor Service lifecycle"""
    
    def __init__(self):
        self.service = None
        self.shutdown_event = asyncio.Event()

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run(self):
        """Run the service with proper lifecycle management"""
        self.setup_signal_handlers()
        
        try:
            logger.info("🚀 Starting Result Ingestor Service Runner...")
            
            self.service = create_result_ingestor_service()
            
            # Run service with shutdown handling
            service_task = asyncio.create_task(self.service.start())
            shutdown_task = asyncio.create_task(self.shutdown_event.wait())
            
            # Wait for either service completion or shutdown signal
            done, pending = await asyncio.wait(
                [service_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Handle service task result
            if service_task in done:
                try:
                    await service_task
                except Exception as e:
                    logger.error(f"❌ Service failed: {e}")
                    raise
            
            logger.info("✅ Service shutdown completed")
            
        except KeyboardInterrupt:
            logger.info("🛑 Received keyboard interrupt")
        except Exception as e:
            logger.error(f"❌ Runner error: {e}")
            raise
        finally:
            if self.service:
                await self.service.stop()


async def main():
    """Main entry point"""
    runner = ServiceRunner()
    await runner.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Process interrupted")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)