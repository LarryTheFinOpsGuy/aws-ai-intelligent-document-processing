import sys
import os
from utils.agentcore_gateway_client import mcp_manager
from utils.retry import invoke_with_retry

from strands import Agent
from utils.config import get_model
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
import logging
import json
import asyncio
from pydantic import BaseModel, Field
from utils.processing_actions import create_action_start, update_action_complete
from utils.job_update_hook import JobUpdateHook



import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class InstructionsAgentNode(MultiAgentBase):
    """Wrapper for instructions agent as a graph node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
        self.name = "Instructions generator agent"
        self.description = "Takes as input s3 uri to extracted text markdown and generates extraction instructions for the document. Returns the s3 uri to the instructions prompt."
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)
    
    def _create_agent(self):
        """Create and configure the instructions agent"""
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
        
        # Load minimal instructions prompt
        system_prompt_file = os.path.join(os.path.dirname(__file__), 'prompts/po_minimal_instructions_prompt.txt')
        with open(system_prompt_file, 'r', encoding='utf-8') as f:
            prompt_generator_system_prompt = f.read()
        schema_file = os.path.join(os.path.dirname(__file__), 'doc_schema/purchase_order_schema.json')
        with open(schema_file, 'r', encoding='utf-8') as f:
            po_schema = f.read()

        return Agent(
            system_prompt=f"""{prompt_generator_system_prompt}

### PO-SCHEMA:
```json
{po_schema}
```

Your workflow:
1. The markdown document content is already provided in your input context 
2. Analyze the markdown text using the prompt generator instructions 
3. Generate a specialized extraction prompt for this specific format
4. Save the specialized prompt to S3 at file_key using the upload_file tool = instructions/[session_id]/extraction_prompt.md - this will be the instructions_s3_uri
5. Use the update_job tool to update the job with instructions_s3_uri = the uri returned for the extraction_prompt.md
6. Return the S3 URI as: INSTRUCTIONS_URI = [S3_uri]

Now tell me your plan, include the fully qualified uri for the files you will create. Then execute the plan

After your analysis format your final response as follows:
<RESPONSE>
<response_message>Response message to user</response_message>
<instructions_uri>S3 URI to instructions extraction prompt</instructions_uri>
</RESPONSE>

IMPORTANT: Always use the update_job tool to update instructions_s3_uri before providing your final response.
""",
            tools=agent_tools,
            model=model,
            conversation_manager=conversation_manager,
            trace_attributes={
                "agent.role": "instructions",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")
        started_at = create_action_start(session_id, "instructions")

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

            # Helper to extract file key from S3 URI
            def get_file_key(s3_uri):
                if not s3_uri or not s3_uri.startswith("s3://"):
                    return None
                parts = s3_uri.replace("s3://", "").split("/", 1)
                return parts[1] if len(parts) > 1 else None

            # Download markdown content and append to task
            if markdown_s3_uri:
                file_key = get_file_key(markdown_s3_uri)
                if file_key:
                    download_result = await asyncio.to_thread(
                        self.agent.tool.agenticidp_s3_bucket_target___download_file,
                        file_key=file_key,
                        record_direct_tool_call=False
                    )
                    
                    # Extract markdown content from download result
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
                        markdown_content = ""
                    
                    # Append markdown content to task
                    if isinstance(task, list):
                        task.append({'text': f"\nDocument markdown content:\n{markdown_content}"})
                    else:
                        task = [
                            {'text': str(task)},
                            {'text': f"\nDocument markdown content:\n{markdown_content}"}
                        ]

            """Execute blueprint agent and return MultiAgentResult"""
            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task, invocation_state=invocation_state, **kwargs)
            
            # Update action record with success
            update_action_complete(session_id, started_at, str(result), success=True)
            
            result_obj = MultiAgentResult(
                status=Status.COMPLETED,
                results={"instructions": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            result_obj.stop_reason = getattr(result, 'stop_reason', None)
            return result_obj

        except Exception as e:
            # Update action record with failure
            update_action_complete(session_id, started_at, str(e), success=False)
            logger.warning(f"Updated action record with failure: {e}")
            raise

