# /agents/master_agent.py

"""
Defines the graph-based Master Agent for orchestrating child agents.
"""
from datetime import datetime, timezone
from typing import Dict, Optional
import uuid
from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from app.core.config import settings
from app.state.graph_state import MasterAgentState, AgentTask
from app.protocols.a2a_interface import AgentInterface
from app.api.v1.schemas.context import ParsedInstructions
from app.services.context_service import get_context
from aiokafka import AIOKafkaProducer
import json
import ssl
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
)
logger = logging.getLogger(__name__)



class RoutedAgent(BaseModel):
    agent_name: str = Field(description="The name of the selected agent to handle the task")

class MasterAgent:
    """
    Represents the Master Agent's workflow, defined as a graph.
    This class holds the logic for the nodes in the LangGraph.
    """

    def __init__(self, agent_registry: Dict[str, AgentInterface]):
        """
        Initializes the MasterAgent with a registry of available child agents.
        
        Args:
            agent_registry: A dictionary mapping agent names to agent instances.
        """
        self.agent_registry = agent_registry

        # Initialize Kafka producer properly
        self.producer = None

        # The "Meta Agent" for parsing instructions
        self.instruction_parser = AzureChatOpenAI(
            model=settings.AZURE_OPENAI_MODEL,
            temperature=0,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        ).with_structured_output(ParsedInstructions)
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at deconstructing user requests into actionable components. Analyze the user's input and extract the core task, any specified persona, formatting requirements, and constraints. Do not attempt to answer the user's request, only parse it."),
            ("human", "User Request: {input}"),
        ])
        self.parser_chain = self.prompt_template | self.instruction_parser

        router_llm = AzureChatOpenAI(
            model=settings.AZURE_OPENAI_MODEL,
            temperature=0,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        )
        self.router_chain = router_llm.with_structured_output(RoutedAgent)

    async def initialize(self):
        """Async initialization method"""
        await self._setup_kafka_producer()

    async def _setup_kafka_producer(self):
        """Setup Kafka producer with proper SSL configuration"""
        try:
            # SSL context for Aiven Kafka
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_REQUIRED

            # Load certificates if using client certificates
            if hasattr(settings, 'KAFKA_SSL_CAFILE') and settings.KAFKA_SSL_CAFILE:
                ssl_context.load_verify_locations(settings.KAFKA_SSL_CAFILE)
            
            if (hasattr(settings, 'KAFKA_SSL_CERTFILE') and settings.KAFKA_SSL_CERTFILE and 
                hasattr(settings, 'KAFKA_SSL_KEYFILE') and settings.KAFKA_SSL_KEYFILE):
                ssl_context.load_cert_chain(settings.KAFKA_SSL_CERTFILE, settings.KAFKA_SSL_KEYFILE)

            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                security_protocol=settings.KAFKA_SECURITY_PROTOCOL,
                ssl_context=ssl_context,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                compression_type="gzip",
                max_batch_size=16384,
                linger_ms=10,
                retry_backoff_ms=100,
                request_timeout_ms=30000,
            )
            
            await self.producer.start()
            logger.info("📤 Kafka producer started for Master Agent")

        except Exception as e:
            logger.error(f"❌ Failed to start Kafka producer: {e}")
            self.producer = None
            raise

    def get_agent_description(self) -> str:
        """
        Returns a string describing the agent's capabilities.
        This description is crucial for the router to make a good decision.
        """
        return "\n".join([
            f"{name}: {agent.get_capabilities()}"
            for name, agent in self.agent_registry.items()
        ])

    def parse_user_request(self, state: MasterAgentState) -> MasterAgentState:
        """NEW ENTRY NODE: Parses the user request and fetches context."""
        print("--- MasterAgent: Parsing user request ---")
        request = state['original_request']
        context_id = state['context_id']

        # Parse instructions
        parsed_instructions = self.parser_chain.invoke({"input": request})
        state['parsed_instructions'] = parsed_instructions

        # Retrieve context if requested
        if context_id:
            context = get_context(context_id)
            if context:
                state['received_context'] = context['content']
                print(f"--- MasterAgent: Successfully retrieved context '{context_id}' ---")

        return state

    def route_to_agent(self, state: MasterAgentState) -> MasterAgentState:
        """
        This node routes the task to the appropriate agent.
        """
        print(f"--- MasterAgent: Routing to agent ---")
        task_description = state['parsed_instructions'].core_task
        agent_descriptions = self.get_agent_description()
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an expert dispatcher. Your job is to select the best agent to perform a specific task based on their capabilities. "
             "Here are the available agents:\n{agent_descriptions}\n\n"
             "Respond with only the name of the agent that should be used."),
            ("human", "Task: {task}")
        ])
        
        routing_chain = prompt | self.router_chain

        result = routing_chain.invoke({
            "agent_descriptions": agent_descriptions,
            "task": task_description
        })

        chosen_agent = result.agent_name
        print(f"--- MasterAgent: Routing to agent {chosen_agent} ---")

        state['chosen_agent_name'] = chosen_agent
        return state

    async def delegate_task(self, state: MasterAgentState) -> MasterAgentState:
        """
        This is the entry node. It decomposes the user request into the first task.
        This node now delegates by producing a message to a Kafka topic.
        
        Note: For this initial version, we will do a simple 1:1 delegation.
        A more advanced version would involve more complex decomposition logic.
        """
        print("--- MasterAgent: Delegating task with dynamic prompt via kafka---")

        # Get the unique ID for this specific graph run
        # conversation_id = config["configurable"]["thread_id"]
        conversation_id = state['conversation_id'] or str(uuid.uuid4())
        agent_name = state['chosen_agent_name']

        if not agent_name or agent_name not in self.agent_registry:
            raise ValueError(f"Router selected an invalid or non-existent agent: {agent_name}")

        # existing_task = await self._get_existing_task(conversation_id)
        # if existing_task:
        #     print(f"--- MasterAgent: Task already exists for conversation {conversation_id} ---")
            
        #     # Check if the existing task is completed
        #     if existing_task['status'] == 'completed':
        #         print(f"--- MasterAgent: Existing task is completed, proceeding to process results ---")
        #         state['decomposed_tasks'].append(existing_task)
        #         state['next_agent'] = "process_results"
        #     elif existing_task['status'] == 'pending':
        #         print(f"--- MasterAgent: Existing task is pending, waiting for results ---")
        #         state['decomposed_tasks'].append(existing_task)
        #         state['next_agent'] = "wait_for_results"
        #     elif existing_task['status'] == 'RUNNING':
        #         print(f"--- MasterAgent: Existing task is running, waiting for results ---")
        #         state['decomposed_tasks'].append(existing_task)
        #         state['next_agent'] = "wait_for_results"
        #     else:
        #         print(f"--- MasterAgent: Existing task has status '{existing_task['status']}', ending ---")
        #         state['decomposed_tasks'].append(existing_task)
        #         state['next_agent'] = "end"
        #     return state
        
        # --- DYNAMIC PROMPT ASSEMBLY ---
        parsed = state['parsed_instructions']
        final_instructions_for_agent = (
            f"Here is the core task you must complete: {parsed.core_task}.\n\n"
            f"Adhere to the following persona: {parsed.persona}.\n"
            f"Follow these formatting requirements: {parsed.format_instructions}.\n"
            f"Obey these constraints: {parsed.constraints}.\n"
        )

        # Add the retrieved context, if it exists, to the instructions.
        if state.get('received_context'):
            final_instructions_for_agent += (
                "\n--- IMPORTANT CONTEXT TO USE ---\n"
                f"{state['received_context']}\n"
                "--- END OF CONTEXT ---\n"
            )

        # Create the task
        task_id = str(uuid.uuid4())

        task = AgentTask(
            task_id=task_id,
            conversation_id=conversation_id,
            task=f"Task for {agent_name}",
            instructions=final_instructions_for_agent,
            agent_name=agent_name,
            status="pending",
            dependencies=[],
            result=None
        )

        # Store the task in the database
        await self._store_task_in_db(task)

        # Add debug logging
        print(f"--- MasterAgent: Task created: {task} ---")
        print(f"--- MasterAgent: Producer status: {self.producer is not None} ---")

        if self.producer is None:
            raise RuntimeError("Kafka producer not initialized. Please call initialize() on the MasterAgent first.")

        try:
            # --- KAFKA INTEGRATION ---
            # Instead of calling an agent directly, produce an event to the 'agent-tasks' topic.
            # print(f"--- MasterAgent: Producing task {task['task_id']} for conversation {conversation_id} to 'agent-tasks' topic ---")
            await self.producer.send("agent-tasks", task)
            await self.producer.flush()
            print(f"--- MasterAgent: Successfully sent task {task['task_id']} for conversation {conversation_id} to 'agent-tasks' topic ---")
        
        except Exception as e:
            print(f"--- MasterAgent: Failed to send task to Kafka: {e} ---")
            raise
        
        state['decomposed_tasks'].append(task)
        # state['next_agent'] = "wait_for_child_result"
        # We can now move to a state that explicitly waits for results.
        state['next_agent'] = "wait_for_results" # The graph pauses here.
        return state

    async def _get_existing_task(self, conversation_id: str) -> Optional[AgentTask]:
        """Check if a task already exists for this conversation"""
        try:
            from app.core.db_client import db_client
            if not db_client.is_connected():
                await db_client.connect()
            
            tasks_collection = await db_client.get_collection("tasks")
            
            task_doc = await tasks_collection.find_one({"conversation_id": conversation_id})
            
            if task_doc:
                results_collection = await db_client.get_collection("ai_responses")
                result_doc = await results_collection.find_one({"task_id": task_doc.get("task_id")})

                # If we have a result, update the task status
                if result_doc:
                    task_doc["status"] = "completed"
                    task_doc["result"] = result_doc.get("result")

                # Normalize status values
                status = task_doc.get("status", "pending")
                if status in ["RUNNING", "running"]:
                    status = "pending"  # Treat RUNNING as pending for workflow purposes

                return AgentTask(
                    task_id=task_doc.get("task_id"),
                    conversation_id=task_doc.get("conversation_id"),
                    task=task_doc.get("task"),
                    instructions=task_doc.get("instructions"),
                    agent_name=task_doc.get("agent_name"),
                    status=task_doc.get("status", "pending"),
                    dependencies=task_doc.get("dependencies", []),
                    result=task_doc.get("result")
                )
            
            return None
            
        except Exception as e:
            print(f"--- MasterAgent: Error checking existing task: {e} ---")
            return None

    async def _store_task_in_db(self, task: AgentTask):
        """Store task in database immediately"""
        try:
            from app.core.db_client import db_client
            if not db_client.is_connected():
                await db_client.connect()
            
            tasks_collection = await db_client.get_collection("tasks")
            
            task_doc = {
                "task_id": task["task_id"],
                "conversation_id": task["conversation_id"],
                "task": task["task"],
                "instructions": task["instructions"],
                "agent_name": task["agent_name"],
                "status": task["status"],
                "dependencies": task["dependencies"],
                "result": task["result"],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await tasks_collection.insert_one(task_doc)
            
        except Exception as e:
            print(f"--- MasterAgent: Error storing task in DB: {e} ---")

    def execute_child_task(self, state: MasterAgentState) -> MasterAgentState:
        """
        Executes the task assigned to the next agent.
        """
        print(f"--- MasterAgent: Executing child task ---")
        # Find the pending task for the next agent
        task_to_execute = next(
            (t for t in state['decomposed_tasks'] if t['status'] == 'pending' and t['agent_name'] == state['next_agent']),
            None
        )
        
        if not task_to_execute:
            print("--- MasterAgent: No pending task found. Ending. ---")
            state['next_agent'] = "end"
            return state

        # Retrieve the agent from the registry
        agent = self.agent_registry[task_to_execute['agent_name']]
        
        # Execute the task (this is our in-memory A2A call)
        result = agent.execute_task(task_to_execute)
        
        # Update the state with the result
        for task in state['decomposed_tasks']:
            if task['task_id'] == task_to_execute['task_id']:
                task['status'] = 'completed'
                task['result'] = result
                break
        
        # For now, we assume one task and then we are done.
        state['next_agent'] = "end"
        return state

    def router(self, state: MasterAgentState) -> str:
        """
        The conditional router that determines the next step.
        """
        print(f"--- MasterAgent: Routing to {state.get('next_agent', 'unknown')} ---")
        next_agent = state['next_agent']

        if next_agent == "end":
            return "end"
        elif next_agent == "wait_for_results":
            return "wait_for_results"
        elif next_agent == "process_results":
            return "process_results"
        elif next_agent == "synthesize_final_results":
            return "synthesize_final_results"
        else:
            print(f"--- MasterAgent: Unknown next_agent '{next_agent}', routing to end ---")
            return "end"

    async def wait_for_results(self, state: MasterAgentState) -> MasterAgentState:
        """
        Wait for child agent results to be available.
        This node checks if results are ready in the database.
        """
        print(f"--- MasterAgent: Waiting for child agent results ---")

        conversation_id = state['conversation_id']

        # Check if any tasks are still pending
        # pending_tasks =[]
        pending_tasks = [t for t in state['decomposed_tasks'] if t['status'] == 'pending']
        # for task in state['decomposed_tasks']:
        #     status = task['status']
        #     if status not in ['completed', 'COMPLETED']:
        #         pending_tasks.append(task)

        if pending_tasks:
            print(f"--- MasterAgent: {len(pending_tasks)} tasks still pending ---")
            state['next_agent'] = "wait_for_results"
        else:
            print(f"--- MasterAgent: All tasks completed, proceeding to process results ---")
            state['next_agent'] = "process_results"

        return state
    
    async def process_results(self, state: MasterAgentState) -> MasterAgentState:
        """
        Process the results from child agents and prepare for final synthesis.
        """
        print(f"--- MasterAgent: Processing child agent results ---")

        # Get completed tasks
        completed_tasks = [t for t in state['decomposed_tasks'] if t['status'] == 'completed']

        if not completed_tasks:
            print("--- MasterAgent: No completed tasks found ---")
            state['next_agent'] = "end"
            return state
        
        results = []
        for task in completed_tasks:
            if task['result']:
                results.append({
                    "agent_name": task['agent_name'],
                    "task_id": task['task_id'],
                    "result": task['result']
                })

        state['child_results'] = results
        state['next_agent'] = "synthesize_final_results"

        print(f"--- MasterAgent: Processed {len(results)} results from child agents---")

        return state

    async def synthesize_final_results(self, state: MasterAgentState) -> MasterAgentState:
        """
        Synthesize the final results from the child agent results.
        """
        print(f"--- MasterAgent: Synthesizing final results ---")

        # Get the child results from the state <> Safety check
        child_results = state.get('child_results', [])
        original_request = state['original_request']
        conversation_id = state['conversation_id']

        if not child_results:
            state['final_result'] = "No results available from child agents."
            state['next_agent'] = "end"
            return state

        # Create a synthesis prompt
        synthesis_prompt = f"""
        Original Request: {original_request}
        
        Child Agent Results:
        """
        
        for result in child_results:
            synthesis_prompt += f"""
        Agent: {result['agent_name']}
        Result: {result['result']}
        """

        synthesis_prompt += """
        
        Please synthesize these results into a coherent final response that addresses the original request.
        """
        
        # Use the instruction parser to synthesize results
        try:
            synthesis_result = self.instruction_parser.invoke({"input": synthesis_prompt})
            state['final_result'] = synthesis_result
        except Exception as e:
            print(f"--- MasterAgent: Error synthesizing results: {e} ---")
            # Fallback: concatenate results
            state['final_result'] = "\n\n".join([r['result'] for r in child_results])

        try:
            from app.services.result_ingestor import create_result_ingestor_service
            result_ingestor = create_result_ingestor_service()
            await result_ingestor.store_final_synthesized_result(
                conversation_id=conversation_id,
                final_result=state['final_result'],
                metadata={
                    "original_request": original_request,
                    "child_agents_used": [r['agent_name'] for r in child_results],
                    "synthesis_method": "llm_synthesis"
                }
            )
        except Exception as e:
            print(f"--- MasterAgent: Error storing final synthesized result: {e} ---")

        
        state['next_agent'] = "end"
        return state

    async def cleanup(self):
        """Cleanup resources"""
        if self.producer:
            await self.producer.stop()
            logger.info("📤 Kafka producer stopped for Master Agent")