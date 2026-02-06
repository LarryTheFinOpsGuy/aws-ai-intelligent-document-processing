import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from common.dynamodb_jobs import DynamoDBJobsClient

def dynamodb_state_tracker(node_name=None):
    """Decorator to track state changes in DynamoDB
    
    Args:
        node_name: Optional node name. If not provided, infers from class name.
    """
    def decorator(invoke_method):
        async def wrapper(self, task, invocation_state=None, **kwargs):
            # Get node name from parameter or infer from class
            name = node_name or self.__class__.__name__.replace('AgentNode', '').lower()
            session_id = invocation_state.get('job_state').get('session_id') if invocation_state else None
            
            if session_id:
                # Import from shared config module
                from utils.config import JOBS_TABLE_NAME
                
                jobs_client = DynamoDBJobsClient(JOBS_TABLE_NAME)
                
                # Before execution
                jobs_client.update_job(
                    session_id,
                    status='starting',
                    agent_name=name,
                    shared_state=json.dumps(invocation_state.get('job_state'))
                )
            
            try:
                result = await invoke_method(self, task, invocation_state, **kwargs)
                
                if session_id:
                    # After successful execution
                    updates = {
                        'status': 'completed',
                        'agent_name': name,
                        'shared_state': json.dumps(invocation_state.get('job_state'))
                    }
                    
                    # Check if agent has custom success handler
                    if hasattr(self, '_get_success_updates') and hasattr(self, '_structured_result'):
                        custom_updates = self._get_success_updates(self._structured_result)
                        updates.update(custom_updates)
                    
                    jobs_client.update_job(session_id, **updates)
                
                return result
                
            except Exception as e:
                if session_id:
                    # After failed execution
                    updates = {
                        'status': 'failed',
                        'agent_name': name,
                        'error_message': str(e),
                        'shared_state': json.dumps(invocation_state.get('job_state'))
                    }
                    
                    # Check if agent has custom error handler
                    if hasattr(self, '_get_error_updates'):
                        custom_updates = self._get_error_updates(e, invocation_state)
                        updates.update(custom_updates)
                    
                    jobs_client.update_job(session_id, **updates)
                
                raise
                
        return wrapper
    return decorator
