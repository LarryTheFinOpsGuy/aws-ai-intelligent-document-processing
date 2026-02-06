import sys
import os
import boto3

# Set global boto3 region FIRST, before any other imports that use boto3
boto3.setup_default_session(region_name=os.environ.get('AWS_REGION'))

from utils.agentcore_gateway_client import mcp_manager
from bedrock_agentcore.identity.auth import requires_access_token
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from strands.multiagent.graph import GraphBuilder
from strands.multiagent import Swarm
from strands.agent.agent_result import AgentResult
from strands.types.content import ContentBlock, Message
from strands import Agent, tool
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.telemetry import StrandsTelemetry
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from utils.invoke_agent_utils import invoke_agent_with_boto3, get_agent_arn
from utils.config import get_model
import json
import asyncio
import uuid
import logging
print("starting orchestrator")

# Configure OpenTelemetry tracing
strands_telemetry = StrandsTelemetry()
strands_telemetry.setup_otlp_exporter()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

logger.info("Starting orchestratorgraph agent")

app = BedrockAgentCoreApp(debug=False)

logger.info("App Initialized")

# Get configuration from SSM
from utils.config import CREATE_JOB_LAMBDA_ARN, JOBS_TABLE_NAME

from analyzer_agent import AnalyzerAgentNode
from instructions_agent import InstructionsAgentNode
from extractor_agent import ExtractorAgentNode
from matcher_agent import MatcherAgentNode
from troubleshooter_agent import TroubleshooterAgentNode
from instructions_fixer_agent import InstructionsFixerAgentNode
from save_instructions_agent import SaveInstructionsAgentNode
from validator_agent import ValidatorAgentNode


class OrchestratorAgent:
    def __init__(self):
        self.wrapper_agent = None
        self.current_session_id = None
        self.active_graphs = {}

    # Conditional functions for graph edges
    def no_match_found(self, state):
        try:
            results = state.results if hasattr(state, 'results') else state
            matcher_result = results.get("matcher")
            if not matcher_result:
                return False
            result_text = str(matcher_result.result if hasattr(matcher_result, 'result') else matcher_result).upper()
            return "NO_MATCH_FOUND" in result_text
        except:
            return False

    def match_found(self, state):
        return not(self.no_match_found(state))

    def extraction_valid(self, state):
        try:
            results = state.results if hasattr(state, 'results') else state
            validator_result = results.get("validator")
            if not validator_result:
                return False
            result_text = str(validator_result.result if hasattr(validator_result, 'result') else validator_result).upper()
            return "ORDER_VALID" in result_text
        except:
            return False

    def extraction_not_valid(self, state):
        return not(self.extraction_valid(state))
       
    def create_orchestrator_graph(self):
        analyzer_agent = AnalyzerAgentNode()
        instructions_agent = InstructionsAgentNode()
        extractor_agent = ExtractorAgentNode()
        matcher_agent = MatcherAgentNode()
        save_instructions_agent = SaveInstructionsAgentNode()
        validator_agent = ValidatorAgentNode()
        troubleshooter_agent = TroubleshooterAgentNode()
        instructions_fixer_agent = InstructionsFixerAgentNode()
        
        
        # New document type inner graph
        new_doc_builder = GraphBuilder()
        new_doc_builder.add_node(instructions_agent, "instructions")
        new_doc_builder.add_node(extractor_agent, "extractor")
        new_doc_builder.add_node(validator_agent, "validator")
        new_doc_builder.add_node(instructions_fixer_agent, "instructions_fixer")
        new_doc_builder.add_node(save_instructions_agent, "save_instructions")
        new_doc_builder.add_edge("instructions", "extractor")
        new_doc_builder.add_edge("extractor", "validator")
        new_doc_builder.add_edge("validator", "instructions_fixer", condition=self.extraction_not_valid)
        new_doc_builder.add_edge("validator", "save_instructions", condition=self.extraction_valid)
        new_doc_builder.add_edge("instructions_fixer", "extractor")
        new_doc_builder.set_entry_point("instructions")
        new_doc_builder.set_max_node_executions(10)
        new_doc_builder.set_execution_timeout(300)    
        new_doc_graph = new_doc_builder.build()


        # PO processing inner graph
        po_process_builder = GraphBuilder()
        po_process_builder.add_node(extractor_agent, "extractor")
        po_process_builder.add_node(validator_agent, "validator")
        po_process_builder.add_node(troubleshooter_agent, "troubleshooter")
        po_process_builder.add_edge("extractor", "validator")
        po_process_builder.add_edge("validator", "troubleshooter", condition=self.extraction_not_valid)
        po_process_builder.add_edge("troubleshooter", "validator")
        po_process_builder.set_entry_point("extractor")
        po_process_builder.set_max_node_executions(10)
        po_process_builder.set_execution_timeout(300)    
        po_process_graph = po_process_builder.build()

        # Outer graph
        outer_graph_builder = GraphBuilder()
        outer_graph_builder.add_node(analyzer_agent, "analyzer")
        outer_graph_builder.add_node(matcher_agent, "matcher")
        outer_graph_builder.add_node(new_doc_graph, "new_doc_graph")
        outer_graph_builder.add_node(po_process_graph, "po_process_graph")
        outer_graph_builder.add_edge("analyzer", "matcher")
        outer_graph_builder.add_edge("matcher", "new_doc_graph", condition=self.no_match_found)
        outer_graph_builder.add_edge("matcher", "po_process_graph", condition=self.match_found)
        outer_graph_builder.set_entry_point("analyzer")
        outer_graph_builder.set_max_node_executions(10)
        outer_graph_builder.set_execution_timeout(300)
        
        return outer_graph_builder.build()

    def build_execution_report(self, result, invocation_state, max_depth=5):
        """Build execution report from graph result with limited recursion depth"""
        def safe_serialize(obj, depth=0):
            if depth >= max_depth:
                return f"<truncated at depth {max_depth}>"
            
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            elif isinstance(obj, dict):
                return {k: safe_serialize(v, depth + 1) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [safe_serialize(item, depth + 1) for item in obj]
            else:
                return str(obj)[:500]  # Truncate long strings
        
        return {
            "status": str(result.status),
            "total_nodes": getattr(result, 'total_nodes', 0),
            "completed_nodes": getattr(result, 'completed_nodes', 0),
            "failed_nodes": getattr(result, 'failed_nodes', 0),
            "execution_time": getattr(result, 'execution_time', 0),
            "token_usage": safe_serialize(getattr(result, 'accumulated_usage', {})),
            "execution_order": [getattr(node, 'node_id', str(node)) for node in getattr(result, 'execution_order', [])],
            "node_results": {
                node_id: {
                    "status": str(getattr(node_result, 'status', 'unknown')),
                    "result": str(getattr(node_result, 'result', ''))[:500]
                }
                for node_id, node_result in getattr(result, 'results', {}).items()
            },
            "invocation_state": safe_serialize(invocation_state)
        }

    async def execute_graph_background(self, session_id, document_uri):
        """Execute graph in background and store results"""
        try:
            # Ensure wrapper agent is initialized for tool calls
            self.setup_wrapper_agent()
            
            # Update job status to PROCESSING
            job_update = self.wrapper_agent.tool.agenticidp_dynamodb_jobs_target___update_job(
                    job_id=session_id,
                    status="PROCESSING",
                    record_direct_tool_call=False
                )
            logger.info(f"Updated job {session_id} status to PROCESSING: {job_update}")

            invocation_state = {"job_state":{
                "session_id": session_id,
                "document_uri": document_uri,
                "markdown_s3_uri": ""
                }
            }
            
            self.active_graphs[session_id] = {"status": "running", "document_uri": document_uri}
            graph_payload = f"""'session_id': {session_id}, 
    'document_uri': {document_uri}, 
    'message': 'You are a the orchestrator of an autonomus mulit-agent system responseible for processing transactional buisness documents to generate valid output for an ERP system. 
    If the sender and document type match a a document type from our system, you will follow the flow outlined for this document type and sender.
    If the document type do not have a match, you will follow the steps to set this up as a new document type, including creating instructions, using the instructions to extract, validating the extraction, and saving the document type
    Now process document_uri. '"""

            graph = self.create_orchestrator_graph()
            result = await graph.invoke_async(graph_payload, invocation_state=invocation_state)
            

            report = self.build_execution_report(result, invocation_state)
            self.active_graphs[session_id] = {"status": "completed", "report": report}
            
            # Update job status to COMPLETED or FAILED based on graph result
            final_status = "COMPLETED" if result.status == Status.COMPLETED else "FAILED"

            job_update = self.wrapper_agent.tool.agenticidp_dynamodb_jobs_target___update_job(
                    job_id=session_id,
                    status=final_status,
                    record_direct_tool_call=False
                )
            logger.info(f"Updated job {session_id} status to {final_status}: {job_update}")
        
            logger.info(f"Graph execution completed for session {session_id}")
            
        except Exception as e:
            self.active_graphs[session_id] = {"status": "failed", "error": str(e)}
            
            # Update job status to FAILED
            job_update = self.wrapper_agent.tool.agenticidp_dynamodb_jobs_target___update_job(
                    job_id=session_id,
                    status="FAILED",
                    record_direct_tool_call=False
                )
            logger.info(f"Updated job failed {job_update}")
            
            logger.error(f"Graph execution failed for session {session_id}: {e}")

    def setup_wrapper_agent(self):
        """Setup the wrapper agent that uses graph as tools"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        model = get_model(model_name="nova_lite")
        conversation_manager = SlidingWindowConversationManager(
            window_size=20,
            should_truncate_results=True
        )

        if self.wrapper_agent is None:
            self.wrapper_agent = Agent(
                system_prompt="""You are a document processing assistant that manages long-running document workflows.

document processing jobs are stored in the jobs table, use the jobs tools to access
job artifacts files can be accessed with the document storage tools
Instructions are stored in the vector bucket

When users ask to process a document:
- Use start_document_processing with the S3 URI
- Return the session_id to the user
- Explain they can check status anytime

When users ask for status:
- Use check_processing_status with their session_id
- Summarize the results in user-friendly language
- If completed, highlight key findings from the report

Be helpful and explain what's happening at each stage.""",
                tools=[check_processing_status] + tools,
                model=model,
                conversation_manager=conversation_manager,
                callback_handler=None,
                trace_attributes={
                    "agent.role": "orchestrator",
                    "agent.type": "wrapper",
                    "workflow.type": "graph",
                    "system": "agenticidp"
                }
            )
        
        return self.wrapper_agent

    async def orchestrate_document_processing_graph(self, payload, context):
        self.current_session_id = getattr(context, 'session_id', None)
        
        logger.info(f"Starting graph orchestration with payload: {payload}")
        
        action = payload.get("action")
        
        if action == "chat":
            # Use wrapper agent for conversational interface
            user_message = payload.get("message")
            
            if not user_message:
                yield {"error": "Missing message for chat action"}
                return
            
            self.setup_wrapper_agent()
            
            # Stream the response
            agent_stream = self.wrapper_agent.stream_async(user_message)
            async for event in agent_stream:
                if "data" in event:
                    yield {"data": event.get('data',"")}
        
        elif action == "orchestrate_graph":
            document_uri = payload.get("s3_uri")
            
            if not document_uri:
                yield {"error": "Missing s3_uri for orchestrate_graph action"}
                return
            
            session_id = self.current_session_id
            
            # Register background task with AgentCore
            task_id = app.add_async_task("graph_execution", {"session_id": session_id})
            logger.info(f"Registered background task with AgentCore - Task ID: {task_id}")
            
            # Run graph in background with proper task tracking
            async def run_graph():
                try:
                    logger.info(f"Starting background graph execution for task {task_id}")
                    await self.execute_graph_background(session_id, document_uri)
                    logger.info(f"Completed background graph execution for task {task_id}")
                finally:
                    app.complete_async_task(task_id)
                    logger.info(f"Marked task {task_id} as complete")
            
            asyncio.create_task(run_graph())
            
            yield {
                "status": "started",
                "session_id": session_id,
                "document_uri": document_uri,
                "message": "Graph execution started in background. Use get_status action to check progress."
            }
        
        elif action == "get_status":
            status_data = self.active_graphs.get(self.current_session_id, {"status": "not_found"})
            
            # Ensure status_data is safely serializable
            def safe_status_serialize(obj, depth=0, max_depth=5):
                if depth >= max_depth:
                    return f"<truncated at depth {max_depth}>"
                
                if isinstance(obj, (str, int, float, bool)) or obj is None:
                    return obj
                elif isinstance(obj, dict):
                    return {k: safe_status_serialize(v, depth + 1, max_depth) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [safe_status_serialize(item, depth + 1, max_depth) for item in obj]
                else:
                    return str(obj)[:200]
            
            yield safe_status_serialize(status_data)
        
        else:
            yield {
                "message": "Graph-based Document Processing Orchestrator",
                "description": "Enhanced orchestrator using Strands Graph pattern for structured workflow management",
                "usage": {
                    "actions": ["chat", "orchestrate_graph", "get_status"],
                    "chat_parameters": {
                        "message": "Natural language message (e.g., 'Process s3://bucket/doc.pdf' or 'What's the status of task abc-123?')"
                    },
                    "orchestrate_graph_parameters": {
                        "s3_uri": "S3 URI of the document to process"
                    }
                },
                "example_requests": [
                    {"action": "chat", "message": "Process document s3://bucket/invoice.pdf"},
                    {"action": "chat", "message": "Check status of task abc-123"},
                    {"action": "orchestrate_graph", "s3_uri": "s3://bucket/document.pdf"}
                ]
            }


# Create instance
orchestrator = OrchestratorAgent()

@tool
def check_processing_status(session_id: str = None) -> str:
    """
    Check status of document processing.
    
    Args:
        session_id: The session ID returned from start_document_processing. 
                 If None, returns status of all processing sessions.
        
    Returns:
        Current status and results (if completed) of the processing session(s)
    """
    if session_id is None:
        # Return all sessions
        return json.dumps({
            "all_sessions": orchestrator.active_graphs,
            "session_count": len(orchestrator.active_graphs)
        }, indent=2)
    
    status = orchestrator.active_graphs.get(session_id, {"status": "not_found", "message": "Session ID not found"})
    return json.dumps(status, indent=2)


# Function-based entrypoint that delegates to class instance
@app.entrypoint
async def orchestrate_document_processing_graph(payload, context):
    print(f"orchestrator invoked with {payload}", flush=True)
    logger.info(f"Received payload: {payload}")
    async for result in orchestrator.orchestrate_document_processing_graph(payload, context):
        yield result

if __name__ == "__main__":
    app.run()
