import sys
import os
from utils.agentcore_gateway_client import mcp_manager
import asyncio
import json

from strands import Agent
from utils.config import get_model
from strands.multiagent.base import MultiAgentBase, NodeResult, Status, MultiAgentResult
from pydantic import BaseModel, Field
import logging
from utils.retry import invoke_with_retry
from utils.processing_actions import create_action_start, update_action_complete
from utils.job_update_hook import JobUpdateHook

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SaveResult(BaseModel):
    response_message: str = Field(description="A response message to the user")
    document_id: str = Field(description="The document ID for the saved/updated document")

class SaveInstructionsAgentNode(MultiAgentBase):
    """Wrapper for save instructions agent as a graph node"""
    
    def __init__(self):
        super().__init__()
        self.agent = self._create_agent()
        self.name = "Save instructions agent"
        self.description = "Takes as input properties from a document along with the instructions and creates or updates a record for the instructions in the database"
    
    def __getattr__(self, name):
        """Delegate all attribute access to internal agent"""
        return getattr(self.agent, name)
    
    def _get_success_updates(self, structured_result):
        """Custom success updates for save instructions agent"""
        return {
            'match_doc_id': structured_result.get('document_id')
        }
    
    
    def _create_agent(self):
        """Create and configure the save instructions agent"""
        mcp_manager.activate_global_context()
        tools = mcp_manager.get_tools()
        
        add_doc_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-vector-target___add_document'), None)
        get_doc_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-vector-target___get_document'), None)
        update_doc_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-vector-target___update_document'), None)
        list_doc_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-vector-target___list_documents'), None)
        search_doc_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-s3-vector-target___search_documents'), None)
        update_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___update_job'), None)
        get_job_tool = next((tool for tool in tools if tool.tool_name == 'agenticidp-dynamodb-jobs-target___get_job'), None)
        
        if not add_doc_tool:
            raise Exception("Required add_document tool not available")
        
        if not update_job_tool:
            logger.warning("Update job tool not available - job updates will be skipped")

        # Include update_job_tool in agent tools list
        agent_tools = [add_doc_tool, get_doc_tool, update_doc_tool, list_doc_tool, search_doc_tool]
        if update_job_tool:
            agent_tools.append(update_job_tool)
        if get_job_tool:
            agent_tools.append(get_job_tool)
        
        model = get_model(model_name="claude_4_5_haiku")
        
        return Agent(
            model=model,
            system_prompt="""You are a Document Storage Specialist.

Your job is to save documents to the vector database with proper metadata.

You will receive the following URIs in your input:
- instructions_uri: The S3 URI of the extraction instructions to use for this document type
- extracted_data_uri: The S3 URI of the extracted JSON data
- markdown_s3_uri: The S3 URI of the markdown version of the document

REQUIRED FIELDS for add_document tool:
- document_type: Type of document (e.g., "PURCHASE ORDER", "INVOICE", "SHIP TICKET")
- sender_name: Name of document sender/originator
- sender_address: Address of document sender/originator. use "No Address" if address is not available
- processing_workflow: "process this as a [document_type] using the provided instructions_s3_uri"
- example_document_uri: Use the document_uri from the original task - this will have a .pdf extension
- instructions_s3_uri: Use the instructions_uri provided in your input

OPTIONAL FIELDS:
- notes: [Always leave this field empty]

VALIDATION REQUIREMENTS:
- All required fields must be present and non-empty
- example_document_uri must be a valid S3 URI (starts with s3://) pointing to the original PDF document
- instructions_s3_uri must be a valid S3 URI (starts with s3://) and should be the instructions_uri

ALWAYS validate all required fields are present before calling the add_document tool.

ALWAYS return the document_id for the saved document in your response

processing_workflow should ALWAYS use the instructions_uri provided in your input and follow this format: 
"process this as a [document_type] using instructions: [instructions_uri]"

First look for any existing records with the same sender_name and sender_address. If one exists, update it. 
If you don't find one, add this doc type

Now tell me your plan, then execute it.

After saving format your final response as follows:
<RESPONSE>
<response_message>A response message to the user</response_message>
<document_id>The document ID for the saved/updated document</document_id>
<markdown_s3_uri>S3 URI of the document text as markdown</markdown_s3_uri>
<instructions_uri>S3 URI to instructions schema</instructions_uri>
</RESPONSE>

IMPORTANT: Always use the update_job tool to update relevant job fields before providing your final response.
""",
            tools=agent_tools,
            trace_attributes={
                "agent.role": "save_instructions",
                "agent.type": "graph_node",
                "workflow.type": "graph",
                "system": "agenticidp"
            }
        )
    
    async def invoke_async(self, task, invocation_state=None, **kwargs):
        import asyncio
        import json
        
        session_id = invocation_state.get("job_state", {}).get("session_id", "no_session_id")
        started_at = create_action_start(session_id, "save_instructions")
        
        try:
            # Get job details to extract instructions_s3_uri and extracted_data_s3_uri (non-blocking)
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
            
            instructions_s3_uri = current_job.get("instructions_s3_uri", "")
            extracted_data_s3_uri = current_job.get("extracted_data_s3_uri", "")
            markdown_s3_uri = current_job.get("markdown_s3_uri", "")
            
            # Inject URIs into task
            if isinstance(task, list):
                task.append({'text': f"\ninstructions_uri: {instructions_s3_uri}"})
                task.append({'text': f"\nextracted_data_uri: {extracted_data_s3_uri}"})
                task.append({'text': f"\nmarkdown_s3_uri: {markdown_s3_uri}"})
            else:
                task = [
                    {'text': str(task)},
                    {'text': f"\ninstructions_uri: {instructions_s3_uri}"},
                    {'text': f"\nextracted_data_uri: {extracted_data_s3_uri}"},
                    {'text': f"\nmarkdown_s3_uri: {markdown_s3_uri}"}
                ]
            
            """Execute save instructions agent and return MultiAgentResult"""
            logger.info(f"invoking agent with {task}")
            result = await invoke_with_retry(self.agent, task, invocation_state=invocation_state, **kwargs)
            
            result_obj = MultiAgentResult(
                status=Status.COMPLETED,
                results={"save_instructions": NodeResult(result=result, status=Status.COMPLETED, execution_count=1)},
                execution_count=1
            )
            result_obj.stop_reason = getattr(result, 'stop_reason', None)
            
            update_action_complete(session_id, started_at, str(result), success=True)
            return result_obj
        except Exception as e:
            update_action_complete(session_id, started_at, str(e), success=False)
            raise


