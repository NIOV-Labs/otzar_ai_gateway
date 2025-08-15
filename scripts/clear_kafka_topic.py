import asyncio
from aiokafka import AIOKafkaConsumer
from app.core.config import settings
import ssl

async def clear_topic():
    """Clear all messages from the agent-tasks topic"""
    
    # SSL context
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    
    consumer = AIOKafkaConsumer(
        "agent-tasks",
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
        ssl_context=ssl_context,
        auto_offset_reset="earliest",
        group_id="clear-topic-group",
        enable_auto_commit=False,  # Don't commit offsets
    )
    
    await consumer.start()
    
    try:
        # Consume all messages without processing them
        async for message in consumer:
            print(f"Clearing message: {message.offset}")
            # Don't process, just consume to clear
    except KeyboardInterrupt:
        print("Stopping topic clearing...")
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(clear_topic())