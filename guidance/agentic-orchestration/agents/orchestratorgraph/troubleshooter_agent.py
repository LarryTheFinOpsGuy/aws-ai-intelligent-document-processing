import sys
import os
from utils.agentcore_gateway_client import mcp_manager
from utils.retry import invoke_with_retry
from utils.processing_actions import create_action_start, update_action_complete
from utils.job_update_hook import JobUpdateHook

from strands import Agent
from utils.config import get_model
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
import logging
import json
import asyncio
from pydantic import BaseModel, Field

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class TroubleshooterAgentNode(MultiAgentBase):
    """Wrapper for troubleshooter agent as a graph node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
        self.name = "Troubleshooter generator agent"
        self.description = "Takes as input s3 uri to extracted text markdown and generates extraction instructions for the document. Returns the s3 uri to the instructions prompt."
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)
    
    def _create_agent(self):
        """Create and configure the troubleshooter agent"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        
        download_file = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-bucket-target___download_file'), None)
        upload_file = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-bucket-target___upload_file'), None)
        update_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___update_job'), None)
        get_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___get_job'), None)
        
        if not update_job_tool:
            logger.warning("Update job tool not available - job updates will be skipped")

        # Include tools in agent tools list
        agent_tools = [download_file, upload_file]
        if update_job_tool:
            agent_tools.append(update_job_tool)
        if get_job_tool:
            agent_tools.append(get_job_tool)

        model = get_model(model_name="claude_4_5_sonnet")

        conversation_manager = SlidingWindowConversationManager(
            window_size=20,
            should_truncate_results=True
        )
        
        # Load PO schema
        system_prompt_file = os.path.join(os.path.dirname(__file__), 'prompts/po_meta_system_prompt.txt')
        with open(system_prompt_file, 'r', encoding='utf-8') as f:
            prompt_generator_system_prompt = f.read()
        schema_file = os.path.join(os.path.dirname(__file__), 'doc_schema/purchase_order_schema.json')
        with open(schema_file, 'r', encoding='utf-8') as f:
            po_schema = f.read()

        return Agent(
            system_prompt=f"""Your job is to identify and fix validation errors in in data that has been converted from markdown to a purchase order JSON.
Review the error message from validation, along with the JSON purchase order and original markdown.

If the validation error is a schema error, try to fix the JSON so it passes schema validaion. 

If there are any content errors, identify if all the data from the markdown was extracted and mapped correctly. If anything was mapped incorrectly, fix the JSON so it can be re-submitted for Validation. 

The original markdown document and current extraction prompt are provided in your input context.


Your workflow:
1. Analyze the validation errors and determine if there was a schema error or content error or both
2. For schema errors, attempt to fix the JSON to pass schema validation
3. For content errors, ensure all data from markdown is correctly mapped in the JSON
4. Use the update_job tool to update the extracted_data_s3_uri field
5. Return the S3 URI as: EXTRACTED_DATA_URI = [S3_uri]

For reference here is the schema for the purchase order:
```json
{po_schema}
```

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
                "agent.role": "troubleshooter",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")
        started_at = create_action_start(session_id, "troubleshooter")
        
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
            extracted_data_s3_uri = current_job.get("extracted_data_s3_uri")

            # Helper to extract file key from S3 URI
            def get_file_key(s3_uri):
                if not s3_uri or not s3_uri.startswith("s3://"):
                    return None
                # Remove s3://bucket-name/ prefix
                parts = s3_uri.replace("s3://", "").split("/", 1)
                return parts[1] if len(parts) > 1 else None

            # Download markdown content (non-blocking)
            markdown_content = ""
            if markdown_s3_uri:
                file_key = get_file_key(markdown_s3_uri)
                if file_key:
                    download_result = await asyncio.to_thread(
                        self.agent.tool.agenticidp_s3_bucket_target___download_file,
                        file_key=file_key,
                        record_direct_tool_call=False
                    )
                    
                    try:
                        response_text = download_result['content'][0]['text']
                        response_data = json.loads(response_text)
                        body_data = json.loads(response_data['body'])
                        file_content = body_data.get('file_content', '')
                        
                        # Decode base64 if needed
                        import base64
                        try:
                            markdown_content = base64.b64decode(file_content).decode('utf-8')
                        except:
                            markdown_content = file_content
                            
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.warning(f"Failed to parse markdown content: {e}")

            # Download extracted content (non-blocking)
            extracted_content = ""
            if extracted_data_s3_uri:
                file_key = get_file_key(extracted_data_s3_uri)
                if file_key:
                    download_result = await asyncio.to_thread(
                        self.agent.tool.agenticidp_s3_bucket_target___download_file,
                        file_key=file_key,
                        record_direct_tool_call=False
                    )
                    
                    try:
                        response_text = download_result['content'][0]['text']
                        response_data = json.loads(response_text)
                        body_data = json.loads(response_data['body'])
                        file_content = body_data.get('file_content', '')
                        
                        # Decode base64 if needed
                        import base64
                        try:
                            extracted_content = base64.b64decode(file_content).decode('utf-8')
                        except:
                            extracted_content = file_content
                            
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        logger.warning(f"Failed to parse extracted content: {e}")

            # Inject content into task
            if isinstance(task, list):
                task.append({'text': f"\nOriginal markdown document:\n{markdown_content}"})
                task.append({'text': f"\nExtracted data:\n{extracted_content}"})
            else:
                task = [
                    {'text': str(task)},
                    {'text': f"\nOriginal markdown document:\n{markdown_content}"},
                    {'text': f"\nExtracted data:\n{extracted_content}"}
                ]

            """Execute troubleshooter agent and return MultiAgentResult"""
            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task, invocation_state=invocation_state, **kwargs)
            
            result_obj = MultiAgentResult(
                status=Status.COMPLETED,
                results={"troubleshooter": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            result_obj.stop_reason = getattr(result, 'stop_reason', None)
            
            update_action_complete(session_id, started_at, str(result), success=True)
            return result_obj
        except Exception as e:
            update_action_complete(session_id, started_at, str(e), success=False)
            raise


