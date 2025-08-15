import os
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.core.config import settings
from app.agents.child_agents.research_agent import ResearchAgent
from app.agents.child_agents.translator_agent import TranslatorAgent

print("Starting ResearchAgent Kafka Worker...")

# --- Create a local registry of all possible agents this worker can be ---
available_agents = {
    "ResearchAgent": ResearchAgent(),
    "TranslatorAgent": TranslatorAgent(),
}
print(f"Worker is capable of running: {list(available_agents.keys())}")

KAFKA_SERVERS = settings.KAFKA_BOOTSTRAP_SERVERS

consumer = AIOKafkaConsumer(
    "agent-tasks",
    bootstrap_servers=KAFKA_SERVERS,
    security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
    ssl_cafile=settings.KAFKA_SSL_CAFILE,
    ssl_certfile=settings.KAFKA_SSL_CERTFILE,
    ssl_keyfile=settings.KAFKA_SSL_KEYFILE,
    auto_offset_reset="earliest",
    group_id="research-agent-group",  # Allows for multiple instances of this worker
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
)


# Producer to send back results
producer = AIOKafkaProducer(
    bootstrap_servers=KAFKA_SERVERS,
    security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
    ssl_cafile=settings.KAFKA_SSL_CAFILE,
    ssl_certfile=settings.KAFKA_SSL_CERTFILE,
    ssl_keyfile=settings.KAFKA_SSL_KEYFILE,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
)


# The worker's main loop
for message in consumer:
    task = message.value
    agent_name = task.get("agent_name")

    # Only process tasks designated for this agent type
    if agent_name in available_agents:
        
        # Select the correct agent object from our local registry
        agent_to_execute = available_agents[agent_name]
        
        print(f"--- Worker: Received task {task['task_id']} for agent '{agent_name}' ---")

        try:
            # Excute the task using the agent's logic
            result = agent_to_execute.execute_task(task)

            # Create a result event
            result_event = {
                "task_id": task['task_id'],
                "conversation_id": task['conversation_id'],
                "status": "completed",
                "result": result
            }

            # Send the result to the 'agent-results topic
            print(f"--- Agent Worker: Sending result for task {task['task_id']} ---") 

            producer.send('agent-results', value=result_event)
            producer.flush()

        except Exception as e:
            print(f"--- Agent Worker: Task {task['task_id']} FAILED. Error: {e} ---")
            error_event = { "task_id": task['task_id'], "status": "failed", "error": str(e) }
            producer.send('agent-results', value=error_event)
            producer.flush()

    else:
        # This task isn't for an agent this worker knows about. Ignore it.
        # In a more advanced system, you might have different worker pools for different agents.
        print(f"--- Agent Worker: Ignoring task {task['task_id']} for unknown agent '{agent_name}' ---")
        pass