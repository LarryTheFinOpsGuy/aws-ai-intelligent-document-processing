import sys
import os
from utils.agentcore_gateway_client import mcp_manager
import base64
import asyncio

from strands import Agent
from strands_tools import use_agent
from utils.config import get_model
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from pydantic import BaseModel, Field
import logging
import json
from urllib.parse import urlparse
from utils.retry import invoke_with_retry
from utils.processing_actions import create_action_start, update_action_complete
from utils.job_update_hook import JobUpdateHook

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ExtractorAgentNode(MultiAgentBase):
    """Wrapper for extractor agent as a graph or swarm node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
        self.name = "Data extraction agent"
        self.description = "Takes as input an s3 uri with markdown text from a document and an s3 uri for instructions. Uses these to extract structured data from the markdown text by following instructions"
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)
    
    def _get_success_updates(self, structured_result):
        """Custom success updates for extractor agent"""
        return {
            'extracted_data_uri': structured_result.get('extracted_data_uri')
        }
    
    async def _get_file_content(self, file_uri):
        """Download file content (non-blocking)"""
        download_result = await asyncio.to_thread(
            self.agent.tool.agenticidp_s3_bucket_target___download_file,
            file_key=urlparse(file_uri).path.lstrip('/') if file_uri.startswith('s3://') else file_uri,
            return_base64=False,
            record_direct_tool_call=False
        )
        
        response_text = download_result['content'][0]['text']
        response_data = json.loads(response_text)
        body_data = json.loads(response_data['body'])
        file_content = body_data.get('file_content', '')

        # Decode base64 if needed
        try:
            content = base64.b64decode(file_content).decode('utf-8')
        except:
            content = file_content  # Fallback if not base64
        return content
    
    def _create_agent(self):
        """Create and configure the extractor agent"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        
        s3_get_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-bucket-target___download_file'), None)
        s3_put_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-bucket-target___upload_file'), None)
        update_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___update_job'), None)
        get_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___get_job'), None)
        guardrail_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-contextual-grounding-target___apply_guardrail'), None)
        
        if not update_job_tool:
            logger.warning("Update job tool not available - job updates will be skipped")

        # Include tools in agent tools list
        agent_tools = [s3_get_tool, s3_put_tool]
        if update_job_tool:
            agent_tools.append(update_job_tool)
        if get_job_tool:
            agent_tools.append(get_job_tool)
        if guardrail_tool:
            agent_tools.append(guardrail_tool)

        model = get_model(model_name="claude_4_5_haiku")

        conversation_manager = SlidingWindowConversationManager(
            window_size=20,
            should_truncate_results=True
        )

        return Agent(
            system_prompt="""
You are a Data Extraction Specialist.
Your job is to extract structured data from markdown documents using instructions.

The markdown document content and instructions are provided in your input context.

Process:
1. Extract data from the markdown text according to the instructions - return JSON for the extracted data. This will only include details from the text document. 
2. Save the extracted JSON data to S3 at /extracted_data/[session_id]/extracted_data.json
3. Use the update_job tool to update the extracted_data_s3_uri field
4. Return the S3 URI as: EXTRACTED_DATA_URI = [S3_uri]

The extracted data should be valid JSON that follows the instructions structure.

Now tell me your plan, include the fully qualified uri for the files you will create. Then execute the plan

After your extraction format your final response as follows:
<RESPONSE>
<response_message>A response message to the user</response_message>
<extracted_data_uri>S3 URI value of EXTRACTED_DATA_URI</extracted_data_uri>
</RESPONSE>

IMPORTANT: Always use the update_job tool to update extracted_data_s3_uri before providing your final response.
            """,
            tools=agent_tools,
            model=model,
            conversation_manager=conversation_manager,
            trace_attributes={
                "agent.role": "extractor",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Invoke extractor agent and return MultiAgentResult"""
        
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")
        started_at = create_action_start(session_id, "extractor")
        
        try:
            # Get job details using get_job tool (non-blocking)
            job_result = await asyncio.to_thread(
                self.agent.tool.agenticidp_dynamodb_jobs_target___get_job,
                job_id=session_id,
                record_direct_tool_call=False
            )
            
            # Extract job data from result
            response_text = job_result['content'][0]['text']
            response_data = json.loads(response_text)
            body_data = json.loads(response_data['body'])
            current_job = body_data['job']
            
            markdown_s3_uri = current_job.get("markdown_s3_uri")
            instructions_s3_uri = current_job.get("instructions_s3_uri")
                

            # Download markdown content (non-blocking)
            markdown_content = await self._get_file_content(markdown_s3_uri)

            # Download instructions content (non-blocking)
            instructions_content = await self._get_file_content(instructions_s3_uri)

                    
            # Create a copy of task and inject content
            task_copy = task.copy()
            task_copy.append({'text': f"\nDocument markdown content:\n{markdown_content}"})
            task_copy.append({'text': f"\nInstructions prompt:\n{instructions_content}"})

            """Execute extractor agent and return MultiAgentResult"""
            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task_copy, invocation_state=invocation_state, **kwargs)
            
            result_obj = MultiAgentResult(
                status=Status.COMPLETED,
                results={"extractor": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            result_obj.stop_reason = getattr(result, 'stop_reason', None)
            
            update_action_complete(session_id, started_at, str(result), success=True)
            return result_obj
        except Exception as e:
            update_action_complete(session_id, started_at, str(e), success=False)
            raise
