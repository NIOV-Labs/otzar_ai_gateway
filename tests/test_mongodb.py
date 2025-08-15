import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from core.db_client import db_client
from core.config import settings

async def test_mongodb_connection():
    """Test MongoDB connection and basic operations"""
    print("🧪 Testing MongoDB Connection...")
    
    try:
        # Test connection (sync)
        db_client.connect()
        print("✅ MongoDB connection successful")
        
        # Test health check (async)
        is_healthy = await db_client.health_check()
        print(f"✅ Health check: {'PASSED' if is_healthy else 'FAILED'}")
        
        # Test collection access
        tasks_collection = db_client.get_collection_sync("tasks")
        contexts_collection = db_client.get_collection_sync("contexts")
        checkpoints_collection = db_client.get_collection_sync("checkpoints")
        print("✅ Collection access successful")
        
        # Test basic CRUD operations (sync operations)
        test_doc = {
            "test_id": "test_connection",
            "message": "MongoDB connection test",
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # Insert test document (sync)
        result = tasks_collection.insert_one(test_doc)
        print(f"✅ Insert test document: {result.inserted_id}")
        
        # Find test document (sync)
        found_doc = tasks_collection.find_one({"test_id": "test_connection"})
        if found_doc:
            print("✅ Find test document: SUCCESS")
        else:
            print("❌ Find test document: FAILED")
        
        # Update test document (sync)
        update_result = tasks_collection.update_one(
            {"test_id": "test_connection"},
            {"$set": {"status": "updated"}}
        )
        print(f"✅ Update test document: {update_result.modified_count} documents modified")
        
        # Delete test document (sync)
        delete_result = tasks_collection.delete_one({"test_id": "test_connection"})
        print(f"✅ Delete test document: {delete_result.deleted_count} documents deleted")
        
        # Test context manager (sync)
        print("🧪 Testing context manager...")
        with db_client:
            collection = db_client.get_collection_sync("tasks")
            count = collection.count_documents({})
            print(f"✅ Context manager test: {count} documents in tasks collection")
        
        # Test async context manager
        print("🧪 Testing async context manager...")
        async with db_client:
            collection = db_client.get_collection_sync("tasks")
            count = collection.count_documents({})
            print(f"✅ Async context manager test: {count} documents in tasks collection")
        
        print("\n🎉 All MongoDB tests passed!")
        
    except Exception as e:
        print(f"❌ MongoDB test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Close connection (async)
        await db_client.close()
        print("🔌 MongoDB connection closed")
    
    return True

def test_config():
    """Test configuration loading"""
    print("🧪 Testing Configuration...")
    
    try:
        # Check if MongoDB settings are loaded
        assert hasattr(settings, 'MONGO_URL'), "MONGO_URL not found in settings"
        assert hasattr(settings, 'MONGO_DB_NAME'), "MONGO_DB_NAME not found in settings"
        
        print(f"✅ MONGO_URL: {settings.MONGO_URL}")
        print(f"✅ MONGO_DB_NAME: {settings.MONGO_DB_NAME}")
        print("✅ Configuration test passed!")
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    return True

async def main():
    """Run all tests"""
    print("🚀 Starting MongoDB Setup Tests\n")
    
    # Test configuration
    config_ok = test_config()
    if not config_ok:
        print("❌ Configuration test failed. Please check your .env file.")
        return
    
    print()
    
    # Test MongoDB connection
    connection_ok = await test_mongodb_connection()
    if not connection_ok:
        print("❌ MongoDB connection test failed. Please check your MongoDB setup.")
        return
    
    print("\n🎉 All tests completed successfully!")
    print("\n📋 Next steps:")
    print("1. Your MongoDB setup is working correctly")
    print("2. You can now run your AI Gateway application")
    print("3. Check docs/MONGODB_SETUP.md for more information")

if __name__ == "__main__":
    asyncio.run(main())
