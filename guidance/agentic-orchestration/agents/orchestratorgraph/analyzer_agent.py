import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.agentcore_gateway_client import mcp_manager

from strands import Agent
from utils.config import get_model
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
import logging
import json
import asyncio
from pydantic import BaseModel, Field
from utils.retry import invoke_with_retry
from utils.processing_actions import create_action_start, update_action_complete
from utils.job_update_hook import JobUpdateHook

session_id = None

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AnalyzerAgentNode(MultiAgentBase):
    """Wrapper for analyzer agent as a graph node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)


    def _create_agent(self):
        """Create and configure the analyzer agent"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        
        textractor_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-textractor-target___extract_text'), None)
        s3_put_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-bucket-target___upload_file'), None)
        update_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___update_job'), None)
        
        model = get_model(model_name="nova_lite")

        conversation_manager = SlidingWindowConversationManager(
            window_size=20,
            should_truncate_results=True
        )

        # Include jobs tool in agent tools list
        agent_tools = [textractor_tool, s3_put_tool, update_job_tool]

        system_prompt = """
You are a Document Identification Specialist responsible for analyzing business documents.

WORKFLOW:
1. You will receive document text that has already been extracted using Textract
2. Analyze the provided markdown text to identify document type and sender information
3. Use the dynamodb_jobs tool to update the processing job with your findings

DOCUMENT TYPES (use exact uppercase values):
- PURCHASE ORDER
- INVOICE
- SHIP TICKET
- UNKNOWN

REQUIRED ACTIONS:
1. Analyze the document_markdown_text provided in your input
2. Identify document type, sender business name and address
3. Use the update_job tool to update the job with doc_type and sender_name fields
4. Format your response in the required XML structure

RESPONSE FORMAT:
<RESPONSE>
<response_message>A response message to the user</response_message>
<document_type>the document type or classification for this document</document_type>
<originator_business_name>The business name of the company that originated the document</originator_business_name>
<originator_business_address>The business address of the company that originated the document</originator_business_address>
</RESPONSE>

IMPORTANT: Always update the job using the update_job tool with doc_type and sender_name before providing your final response. Do not change the status using update_job.
"""

        return Agent(
            system_prompt=system_prompt,
            tools=agent_tools,
            model=model,
            conversation_manager=conversation_manager,
            hooks=[JobUpdateHook()],
            trace_attributes={
                "agent.role": "analyzer",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute analyzer agent and return MultiAgentResult"""
        global session_id
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")
        started_at = create_action_start(session_id, "analyzer")
        document_uri = invocation_state.get("job_state", {}).get("document_uri", "")

        try:
            # STEP 1: Direct textract tool call (non-blocking)
            textract_result = await asyncio.to_thread(
                self.agent.tool.agenticidp_textractor_target___extract_text,
                document_uri=document_uri,
                record_direct_tool_call=False
            )
            # Extract markdown content from textract result
            md_content = textract_result.get("content", [{}])[0].get('text', '')
            try:
                outer_response = json.loads(md_content)
                body_data = json.loads(outer_response.get('body', '{}'))
                extracted_text = body_data.get('extracted_text', md_content)
            except (json.JSONDecodeError, KeyError) as e:
                extracted_text = md_content

            # STEP 2: Save extracted text to S3 (non-blocking)
            save_path = f"projects/{session_id}/extracted_text.md"
            s3_result = await asyncio.to_thread(
                self.agent.tool.agenticidp_s3_bucket_target___upload_file,
                file_key=save_path,
                file_content=extracted_text,
                content_type="text/markdown",
                record_direct_tool_call=False
            )
            
            # Extract S3 URI from result
            try:
                response_text = s3_result['content'][0]['text']
                response_data = json.loads(response_text)
                body_data = json.loads(response_data['body'])
                markdown_s3_uri = body_data['s3_uri']
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                logger.warning(f"Failed to parse S3 URI, using path: {e}")
                markdown_s3_uri = save_path

            # STEP 3: Update job with markdown S3 URI (non-blocking)
            job_update_result = await asyncio.to_thread(
                self.agent.tool.agenticidp_dynamodb_jobs_target___update_job,
                job_id=session_id,
                markdown_s3_uri=markdown_s3_uri,
                record_direct_tool_call=True
            )

            # STEP 4: Append textract results to task content blocks
            if isinstance(task, list):
                task.append({'text': f"\ndocument_markdown_text: {extracted_text}"})
            else:
                task = [
                    {'text': str(task)},
                    {'text': f"\ndocument_markdown_text: {extracted_text}"}
                ]

            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task, invocation_state=invocation_state, **kwargs)
            
            # Validate document type from job state
            current_job = invocation_state.get('current_job', {})
            doc_type = current_job.get('doc_type', '').strip().upper()
            
            if doc_type not in ('PURCHASE ORDER', 'INVOICE', 'SHIP TICKET'):
                error_msg = (
                    f"Document type identification failed. "
                    f"Analyzer could not determine a valid business document type. "
                    f"Found: {doc_type or 'None'}"
                )
                logger.warning(error_msg)
                
                # Update action record with failure
                update_action_complete(session_id, started_at, error_msg, success=False)
                
                # Raise exception to stop graph execution (fail-fast behavior)
                raise ValueError(error_msg)
            
            logger.info(f"Document type identified: {doc_type}")
            
            if hasattr(result, 'state') and result.state:
                result.state.update(invocation_state)
            else:
                result.state = invocation_state
            
            
            # Update action record with success
            update_action_complete(session_id, started_at, str(result), success=True)
            
            analysis_result = MultiAgentResult(
                status=Status.COMPLETED,
                results={"analyzer": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            analysis_result.stop_reason = getattr(result, 'stop_reason', None)
            return analysis_result

        except Exception as e:
            # Update action record with failure
            update_action_complete(session_id, started_at, str(e), success=False)
            logger.warning(f"Updated action record with failure: {e}")
            raise


