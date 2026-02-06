import sys
import os
from utils.agentcore_gateway_client import mcp_manager

from strands import Agent
from utils.config import get_model
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from pydantic import BaseModel, Field
import logging
import json
from utils.retry import invoke_with_retry
from utils.processing_actions import create_action_start, update_action_complete
from utils.job_update_hook import JobUpdateHook

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class MatcherAgentNode(MultiAgentBase):
    """Wrapper for matcher agent as a graph node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)
    
    def _get_success_updates(self, structured_result):
        """Custom success updates for matcher agent"""
        return {
            'match_doc_id': structured_result.get('document_id')
        }
    
    def _create_agent(self):
        """Create and configure the matcher agent"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        
        search_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-vector-target___search_documents'), None)
        update_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___update_job'), None)
        
        if not search_tool:
            raise Exception("Required search tool not available")
        
        if not update_job_tool:
            logger.warning("Update job tool not available - job updates will be skipped")
        
        # Include update_job_tool in agent tools list
        agent_tools = [search_tool]
        if update_job_tool:
            agent_tools.append(update_job_tool)
        
        model = get_model(model_name="nova_lite")
        
        return Agent(
            model=model,
            system_prompt="""You are a Document Matching Specialist.

Your job is to search the vector database for documents similar to the analyzed document and determine if any match is close-to-perfect.

First search for similar documents using this information:
- Document Type
- Business Name 
- Business Address
- Original Document S3 URI
- Status = ACTIVE

Then analyze the results and determine if there is a match in the result set. If you get an empty result set 

MATCHING CRITERIA:
- Document type match exactly - score 1 for exact match, 0 if not a match
- Business name should be identical or very similar with only differences in suffix or abbreviation - score 1 for exact match, 0.9 for same name but with abreviation or difference in prefix, 0 for a different name
- Business address should be very similar with only small variation - score 1 for exact match, 0.9 for close match, 0 for different city, state
- Similarity - score using the value returned 

CONFIDENCE SCORE CALCULATION CRITERIA:
- Add scores from matching criteria. 
- Total score should be 3.7 or above for a positive match
- Total score below 3.7 is no match

REQUIRED ACTIONS:
1. Search for similar documents using the search tool
2. Analyze results and calculate confidence scores
3. Use the update_job tool to update match_doc_id and instructions_s3_uri fields:
   - If match found: set match_doc_id to the document ID and instructions_s3_uri from matched record
   - If no match: set match_doc_id to "NO_MATCH"
4. Format your final response

If you find a match, make sure the record has an instructions_s3_uri and return the matching record including the document_id

Otherwise, return NO_MATCH_FOUND

Now tell me your plan, then execute it.

After your matching format your final response as follows:

If the result is NO_MATCH_FOUND
<RESPONSE>
<result>NO_MATCH_FOUND</result>
<response_message>A response message to the user</response_message>
<confidence_score_calculation>Detail result for your confidence score calcuation reasoning</confidence_score_calculation>
</RESPONSE>

if there is a match

<RESPONSE>
<result>MATCH_FOUND</result>
<response_message>A response message to the user</response_message>
<confidence_score_calculation>Detail result for your confidence score calcuation reasoning</confidence_score_calculation>
<document_id>The document ID for the matched document</document_id>
<processing_workflow>[processing_workflow value]</processing_workflow>
<instructions_s3_uri>[full S3 URI of the instructions/extraction_prompt.md]</instructions_s3_uri>
</RESPONSE>

IMPORTANT: Always use the update_job tool to update match_doc_id and instructions_s3_uri before providing your final response.

""",
            tools=agent_tools,
            hooks=[JobUpdateHook()],
            trace_attributes={
                "agent.role": "matcher",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Invoke matcher agent and return result"""
        
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")

        # Create action record with start time
        started_at = create_action_start(session_id, "matcher")

        try:
            """Execute matcher agent and return MultiAgentResult"""
            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task, invocation_state=invocation_state, **kwargs)
            
            
            # Update action record with success
            update_action_complete(session_id, started_at, str(result), success=True)
            
            result_obj = MultiAgentResult(
                status=Status.COMPLETED,
                results={"matcher": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            result_obj.stop_reason = getattr(result, 'stop_reason', None)
            return result_obj

        except Exception as e:
            # Update action record with failure
            update_action_complete(session_id, started_at, str(e), success=False)
            logger.warning(f"Updated action record with failure: {e}")
            raise

