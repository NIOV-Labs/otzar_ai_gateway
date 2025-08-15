# run_agent_worker.py
#!/usr/bin/env python3
"""
Agent Worker Runner Script

Usage:
    python run_agent_worker.py --workers 3 --worker-id custom-worker
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.workers.agent_worker import create_worker, create_worker_pool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('agent_worker.log')
    ]
)

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Kafka Agent Worker Runner')
    
    parser.add_argument(
        '--workers', 
        type=int, 
        default=1,
        help='Number of worker instances to run (default: 1)'
    )
    
    parser.add_argument(
        '--worker-id',
        type=str,
        help='Custom worker ID (only used with single worker)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


async def run_single_worker(worker_id: str = None):
    """Run a single worker instance"""
    logger.info(f"🚀 Starting single worker: {worker_id or 'auto-generated'}")
    
    worker = create_worker(worker_id=worker_id)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("🛑 Worker interrupted by user")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")
        raise


async def run_worker_pool(num_workers: int):
    """Run multiple workers in a pool"""
    logger.info(f"🚀 Starting worker pool with {num_workers} workers")
    
    pool = create_worker_pool(num_workers=num_workers)
    
    try:
        await pool.start()
    except KeyboardInterrupt:
        logger.info("🛑 Worker pool interrupted by user")
    except Exception as e:
        logger.error(f"❌ Worker pool failed: {e}")
        raise


async def main():
    """Main entry point"""
    args = parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        if args.workers == 1:
            await run_single_worker(worker_id=args.worker_id)
        else:
            if args.worker_id:
                logger.warning("--worker-id ignored when running multiple workers")
            await run_worker_pool(num_workers=args.workers)
            
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
