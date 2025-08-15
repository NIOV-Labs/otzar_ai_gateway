import os
import asyncio
from typing import Optional
import logging
from pymongo import AsyncMongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBClient:
    def __init__(self):
        self.client: Optional[AsyncMongoClient] = None
        self.db = None
        self._is_connected = False

    async def connect(self):
        """Initialize MongoDB connection with proper configuration"""
        try:
            mongo_uri = settings.MONGO_URL
            self.client = AsyncMongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,         # 10 second connection timeout
                socketTimeoutMS=10000,          # 10 second socket timeout
                maxPoolSize=10,                 # Connection pool size
                minPoolSize=1,                  # Minimum connections in pool
                maxIdleTimeMS=30000,            # Max idle time for connections
                retryWrites=True,               # Enable retry for write operations
                retryReads=True,                # Enable retry for read operations
            )
            
            # Test the connection (async)
            await self.client.admin.command('ping')
            self.db = self.client[settings.MONGO_DB_NAME]
            self._is_connected = True
            logger.info(f"✅ Connected to MongoDB: {settings.MONGO_DB_NAME}")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            self._is_connected = False
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
            self._is_connected = False
            raise

    async def get_collection(self, collection_name: str):
        """Get a MongoDB collection"""
        if not self._is_connected:
            raise ConnectionError("MongoDB client is not connected")
        return self.db[collection_name]
        
    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self._is_connected = False
            logger.info("🔌 MongoDB connection closed")

    def is_connected(self) -> bool:
        """Check if the client is connected"""
        return self._is_connected

    async def health_check(self) -> bool:
        """Perform a health check on the MongoDB connection"""
        try:
            if not self.client:
                return False
            # Ping the database (async)
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

# Global instance
db_client = MongoDBClient()