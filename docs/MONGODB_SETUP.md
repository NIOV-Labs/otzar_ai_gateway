# MongoDB Setup Guide

## Overview
This project uses MongoDB as the primary database for storing:
- Task states and results
- Context documents
- LangGraph checkpoints
- Agent workflow states

## Configuration

### Environment Variables
Add the following variables to your `.env` file:

```bash
# MongoDB Configuration
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=ai_gateway
```

### Connection String Examples

1. **Local MongoDB (default)**
   ```
   MONGO_URL=mongodb://localhost:27017
   ```

2. **MongoDB Atlas (cloud)**
   ```
   MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net
   ```

3. **MongoDB with Authentication**
   ```
   MONGO_URL=mongodb://username:password@host:port
   ```

4. **MongoDB with SSL/TLS**
   ```
   MONGO_URL=mongodb://username:password@host:port/?ssl=true&ssl_cert_reqs=CERT_NONE
   ```

## Database Collections

The application automatically creates the following collections:

- **`tasks`** - Stores task states and results
- **`contexts`** - Stores context documents for agents
- **`checkpoints`** - Stores LangGraph checkpoints for workflow state

## Usage

### Basic Connection
```python
from app.core.db_client import db_client

# Connect to MongoDB (sync)
db_client.connect()

# Get a collection (sync)
collection = db_client.get_collection_sync("tasks")

# Close connection (async)
await db_client.close()
```

### Context Manager Usage
```python
from app.core.db_client import db_client

# Sync context manager
with db_client:
    collection = db_client.get_collection_sync("tasks")
    # Your database operations here

# Async context manager
async with db_client:
    collection = db_client.get_collection_sync("tasks")
    # Your database operations here
```

### Health Check
```python
# Check if connected
if db_client.is_connected():
    print("MongoDB is connected")

# Perform health check (async)
is_healthy = await db_client.health_check()

# Perform health check (sync)
is_healthy = db_client.health_check_sync()
```

### Async Operations with Sync PyMongo
The client uses sync PyMongo but provides async compatibility by wrapping operations in executors:

```python
import asyncio

# In async services, sync operations are wrapped automatically
async def my_service():
    # This uses run_in_executor internally for async compatibility
    result = await get_context("my_context")
    
# Or manually wrap sync operations
async def manual_async_operation():
    collection = db_client.get_collection_sync("tasks")
    result = await asyncio.get_event_loop().run_in_executor(
        None, collection.find_one, {"id": "task_123"}
    )
```

## Features

### Connection Pooling
- **Max Pool Size**: 10 connections
- **Min Pool Size**: 1 connection
- **Max Idle Time**: 30 seconds
- **Connection Timeout**: 10 seconds
- **Server Selection Timeout**: 5 seconds

### Error Handling
- Automatic retry for read/write operations
- Connection failure detection
- Graceful error handling with detailed logging

### Security
- SSL/TLS support
- Authentication support
- Connection string validation

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Check if MongoDB is running
   - Verify connection string format
   - Check network connectivity

2. **Authentication Failed**
   - Verify username/password in connection string
   - Check database permissions

3. **SSL Certificate Issues**
   - Add `ssl_cert_reqs=CERT_NONE` to connection string for self-signed certificates
   - Verify certificate paths

### Debug Mode
Enable debug logging by setting:
```python
import logging
logging.getLogger("pymongo").setLevel(logging.DEBUG)
```

## Performance Tips

1. **Indexes**: Create indexes on frequently queried fields
2. **Connection Pooling**: The client automatically manages connection pooling
3. **Batch Operations**: Use bulk operations for multiple documents
4. **Projection**: Only retrieve needed fields using projection

## Example Indexes
```javascript
// Create indexes for better performance
db.tasks.createIndex({"conversation_id": 1})
db.contexts.createIndex({"context_id": 1})
db.checkpoints.createIndex({"thread_id": 1})
```
