import boto3
import json
import uuid
import time
import logging

logger = logging.getLogger(__name__)

def parse_streaming_response(response_text: str) -> dict:
    """Parse streaming response (SSE format) or regular JSON."""
    try:
        # Handle Server-Sent Events format
        if response_text.strip().startswith('data: '):
            # Extract JSON from SSE format: "data: {...}"
            lines = response_text.strip().split('\n')
            for line in lines:
                if line.startswith('data: '):
                    json_data = line[6:]  # Remove "data: " prefix
                    return json.loads(json_data)
            return {"error": f"No data found in SSE response: '{response_text}'"}
        else:
            # Regular JSON response
            return json.loads(response_text)
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {e}, Response: '{response_text}'"}

def invoke_agent_with_boto3(agent_arn, payload, session_id=None):
    """Invoke an AgentCore Runtime agent via boto3 with action-based polling"""
    client = boto3.client('bedrock-agentcore')
    
    # Use provided session_id or generate new one
    if not session_id:
        session_id = str(uuid.uuid4())
    
    try:
        # Start the task
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(payload).encode(),
            runtimeUserId="orchestrator_agent"
        )
        
        response_text = response['response'].read().decode('utf-8')
        initial_result = parse_streaming_response(response_text)
        logger.info(f"Initial response: {initial_result}")
        
        # Check if this is an async task (has processing status)
        extraction_status = initial_result.get('extraction_status')
        if extraction_status == 'processing':
            # Poll for completion using action-based approach
            return poll_task_completion(client, agent_arn, session_id)
        else:
            # Synchronous response
            return initial_result
        
    except Exception as e:
        logger.warning(f"Error invoking agent {agent_arn}: {e}", exc_info=True)
        raise e

def poll_task_completion(client, agent_arn, session_id, max_wait=120, poll_interval=5):
    """Poll async task until completion using action-based status checks"""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            status_payload = {'action': 'get_status'}
            
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(status_payload).encode(),
                runtimeUserId='orchestrator_agent'
            )
            
            response_text = response['response'].read().decode('utf-8')
            result = parse_streaming_response(response_text)
            
            # Check for different status formats
            active_count = result.get('active_count', 0)
            extraction_status = result.get('extraction_status', '')
            
            if active_count == 0 or extraction_status in ['completed', 'failed']:
                if extraction_status == 'failed':
                    raise Exception(f"Task failed: {result.get('error', 'Unknown error')}")
                
                # Get structured result
                return get_structured_result(client, agent_arn, session_id)
            
            elapsed = int(time.time() - start_time)
            logger.info(f"Polling status [{elapsed}s]: {active_count} active tasks")
                
        except Exception as e:
            if 'Task failed:' in str(e):
                raise e
            logger.warning(f"Poll error: {e}")
            
        time.sleep(poll_interval)
    
    raise Exception(f"Timeout waiting for task to complete")

def get_structured_result(client, agent_arn, session_id):
    """Get structured result using action-based approach"""
    try:
        result_payload = {'action': 'get_structured_result'}
        
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(result_payload).encode(),
            runtimeUserId='orchestrator_agent'
        )
        
        response_text = response['response'].read().decode('utf-8')
        result = parse_streaming_response(response_text)
        logger.info(f"Structured result: {result}")
        
        return result
        
    except Exception as e:
        logger.warning(f"Error getting structured result: {e}")
        raise e

def get_agent_arn(agent_name):
    """Retrieve agent ARN from Parameter Store"""
    try:
        ssm = boto3.client('ssm')
        response = ssm.get_parameter(Name=f'/agenticidp/agents/{agent_name}_arn')
        return response['Parameter']['Value']
    except Exception as e:
        logger.warning(f"Error getting agent ARN for {agent_name}: {e}")
        raise e
