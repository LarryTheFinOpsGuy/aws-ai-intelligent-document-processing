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
from typing import Literal


import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ValidatorAgentNode(MultiAgentBase):
    """Wrapper for validator agent as a graph node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
        self.name = "Purchase Order Validation agent"
        self.description = "Takes as input the s3 uri to a purchas order json file and validates the schema and values in the purchase order"
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)
    
    def _create_agent(self):
        """Create and configure the validator agent"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        
        po_validator_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-po-validator-target___validate_purchase_order'), None)
        update_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___update_job'), None)
        get_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___get_job'), None)
        
        # Include tools in agent tools list
        agent_tools = [po_validator_tool]
        if update_job_tool:
            agent_tools.append(update_job_tool)
        if get_job_tool:
            agent_tools.append(get_job_tool)

        model = get_model(model_name="claude_4_5_haiku")

        conversation_manager = SlidingWindowConversationManager(
            window_size=20,
            should_truncate_results=True
        )

        return Agent(
            system_prompt="""You are a purchase order validation agent.

The extracted data is provided in your input context.

Your workflow:
1. Validate the extracted data using the PO validator tool
2. Analyze the validation result and decide:

**ORDER_VALID** - Choose this if:
- Schema validation passed AND SKUs exist AND options exist
- Validation has no ERROR messages
- WARNING is acceptable

**ORDER_NOT_VALID** - Choose this if:
- Schema validation failed
- SKUs don't exist in the system
- Product options (colors, sizes) don't exist in the system
- Vendor information is invalid
- Any ERROR with "not available" or "not found" messages

Execute this workflow when given a task.

After your validation format your final response as follows:
<RESPONSE>
<response_message>Response message to user</response_message>
<validation_result>Validation result from PO validator tool</validation_result>
<validation_status>ORDER_VALID or ORDER_NOT_VALID</validation_status>
</RESPONSE>

IMPORTANT: Always use the update_job tool to update validation results before providing your final response.
""",
            tools=agent_tools,
            model=model,
            conversation_manager=conversation_manager,
            trace_attributes={
                "agent.role": "validator",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")
        started_at = create_action_start(session_id, "validator")
        
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
            
            extracted_data_s3_uri = current_job.get("extracted_data_s3_uri")

            # Inject S3 URI into task
            if isinstance(task, list):
                task.append({'text': f"\nExtracted data S3 URI: {extracted_data_s3_uri}"})
            else:
                task = [
                    {'text': str(task)},
                    {'text': f"\nExtracted data S3 URI: {extracted_data_s3_uri}"}
                ]

            """Execute validator agent and return MultiAgentResult"""
            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task, invocation_state=invocation_state, **kwargs)
            
            result_obj = MultiAgentResult(
                status=Status.COMPLETED,
                results={"validator": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            result_obj.stop_reason = getattr(result, 'stop_reason', None)
            
            update_action_complete(session_id, started_at, str(result), success=True)
            return result_obj
        except Exception as e:
            update_action_complete(session_id, started_at, str(e), success=False)
            raise
