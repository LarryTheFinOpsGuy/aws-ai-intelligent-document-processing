"""Shared JobUpdateHook for multi-agent workflow."""
import logging
import json
import os
from strands.hooks import HookProvider, HookRegistry, AfterToolCallEvent, BeforeToolCallEvent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class JobUpdateHook(HookProvider):
    """Hook to update invocation_state with job records from update_job tool calls"""
    
    def __init__(self, session_id: str = None, tool_name: str = None):
        logger.info("Initializing JobUpdateHook")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Tool Name: {tool_name}")
        self.session_id = session_id
        self.tool_name = tool_name  # Optional: specific tool to monitor
    
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self.validate_tool_params)
        registry.add_callback(AfterToolCallEvent, self.update_job_state)
    
    def validate_tool_params(self, event: BeforeToolCallEvent) -> None:
        """Validate and filter tool parameters before execution"""
        logger.info(f"Processing update_job tool result for invocation_state {event}")
        tool_name = event.tool_use.get('name')
        
        # Only process update_job tool calls
        if tool_name != 'agenticidp-dynamodb-jobs-target___update_job':
            return
        
        # Get the input parameters
        tool_input = event.tool_use.get('input', {})
        
        # Check if status is being passed
        if 'status' in tool_input:
            logger.warning(f"Removing 'status' parameter from update_job call. Value was: {tool_input['status']}")
            # Remove status from the input
            filtered_input = {k: v for k, v in tool_input.items() if k != 'status'}
            # Update the tool_use with filtered input
            event.tool_use['input'] = filtered_input
            logger.info(f"Filtered tool input: {filtered_input}")
    
    def update_job_state(self, event: AfterToolCallEvent) -> None:
        """Update invocation_state with job record from update_job results"""
        tool_name = event.tool_use.get('name')
        
        # Handle different tool types
        if tool_name == 'agenticidp-dynamodb-jobs-target___update_job':
            self._handle_update_job(event)
        elif tool_name == 'agenticidp-s3-bucket-target___upload_file':
            self._handle_upload_file(event)
        elif tool_name == 'agenticidp-s3-vector-target___search_documents':
            self._handle_search_documents(event)
    
    def _handle_update_job(self, event: AfterToolCallEvent) -> None:
        """Handle update_job tool results"""
        logger.info(f"Processing update_job tool result for invocation_state {event}")
        #logger.info(f"Processing update_job tool result for invocation_state {event.invocation_state}")
        
        try:
            # Extract job record from update result
            response_text = event.result['content'][0]['text']
            response_data = json.loads(response_text)
            body_data = json.loads(response_data['body'])
            current_job = body_data['job']
            
            # Update invocation_state
            event.invocation_state['current_job'] = current_job
            logger.info(f"Updated invocation_state with current job: {current_job}")
            
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning(f"Failed to parse job record from update result: {e}")
    
    def _handle_upload_file(self, event: AfterToolCallEvent) -> None:
        """Handle upload_file tool results"""
        logger.info("Processing upload results for job update")
    
    def _handle_search_documents(self, event: AfterToolCallEvent) -> None:
        """Handle search_documents tool results"""
        logger.info("Processing search results for job update")
