#!/usr/bin/env python3
"""
Lambda function for UI chat API.
Invokes Bedrock AgentCore orchestrator runtime for conversational interactions.
Handles streaming responses from AgentCore with proper error handling and timeout management.
"""

import json
import os
import boto3
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def decimal_default(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def create_cors_headers():
    """Create standard CORS headers for API responses."""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Session-Id,X-Request-Id,X-Amz-Security-Token,X-Amz-User-Agent',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Credentials': 'false'
    }


def create_error_response(status_code, error_type, message, details=None):
    """Create standardized error response."""
    error_body = {
        'error': error_type,
        'message': message
    }
    if details:
        error_body['details'] = details
    
    return {
        'statusCode': status_code,
        'headers': create_cors_headers(),
        'body': json.dumps(error_body)
    }


def validate_request_body(body):
    """Validate and parse request body."""
    if not body:
        raise ValueError("Request body is required")
    
    try:
        parsed_body = json.loads(body) if isinstance(body, str) else body
    except json.JSONDecodeError:
        raise ValueError("Request body must be valid JSON")
    
    message = parsed_body.get('message', '').strip()
    if not message:
        raise ValueError("Message field is required and cannot be empty")
    
    return message, parsed_body


def extract_session_id(headers):
    """Extract session ID from request headers or generate a new one."""
    headers = headers or {}
    session_id = headers.get('X-Session-Id') or headers.get('x-session-id')
    
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info(f"Generated new session ID: {session_id}")
    else:
        logger.info(f"Using provided session ID: {session_id}")
    
    return session_id


def process_streaming_response(response):
    """
    Process streaming response from AgentCore.
    Handles the streaming response format from invoke_agent_runtime.
    """
    agent_response = ""
    
    try:
        # Check if response has a streaming response
        if 'response' in response:
            response_stream = response['response']
            
            # Process streaming lines
            for chunk in response_stream.iter_lines():
                if chunk:
                    line = chunk.decode('utf-8')
                    
                    # Handle data lines with 'data: ' prefix
                    if line.startswith('data: '):
                        data_str = line[6:]  # Remove 'data: ' prefix
                        try:
                            data = json.loads(data_str)
                            
                            # Handle streaming text chunks
                            if 'data' in data and isinstance(data['data'], str):
                                agent_response += data['data']
                            elif isinstance(data, str):
                                agent_response += data
                        except json.JSONDecodeError:
                            # If not JSON, treat as plain text
                            agent_response += data_str
                    elif line.strip():
                        # Handle other non-empty lines
                        try:
                            data = json.loads(line)
                            if 'data' in data:
                                agent_response += data['data']
                            elif 'text' in data:
                                agent_response += data['text']
                        except json.JSONDecodeError:
                            # If not JSON, treat as plain text
                            agent_response += line
                            
        elif 'outputText' in response:
            agent_response = response['outputText']
        elif 'body' in response:
            # Handle response body
            body = response['body']
            if isinstance(body, bytes):
                agent_response = body.decode('utf-8')
            else:
                agent_response = str(body)
        else:
            # Fallback - convert entire response to string
            agent_response = json.dumps(response)
            
    except Exception as e:
        logger.warning(f"Error processing streaming response: {e}", exc_info=True)
        raise ValueError(f"Failed to process agent response: {str(e)}")
    
    return agent_response


def invoke_agent_runtime(orchestrator_arn, session_id, message):
    """
    Invoke Bedrock AgentCore runtime with proper error handling.
    Uses InvokeAgentRuntime API with session context.
    """
    try:
        # Initialize Bedrock AgentCore client
        agentcore_client = boto3.client('bedrock-agentcore')
        
        # Prepare the request payload for AgentCore
        # The orchestrator expects a payload with action and message
        agent_payload = {
            'action': 'chat',
            'message': message
        }
        
        logger.info(f"Invoking agent runtime: {orchestrator_arn}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Payload: {json.dumps(agent_payload)}")
        
        # Invoke the agent runtime
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=orchestrator_arn,
            runtimeSessionId=session_id,
            payload=json.dumps(agent_payload),
            runtimeUserId="ui-chat-user"
        )
        
        logger.info("Agent runtime invoked successfully")
        
        return response
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.warning(f"AgentCore error: {error_code} - {error_message}")
        raise


def lambda_handler(event, context):
    """
    Handle POST /api/chat request with API Gateway proxy integration.
    Sends message to AgentCore orchestrator and returns streaming response.
    
    Request Body:
    - message: User message text (required)
    - action: Optional action type (defaults to 'chat')
    
    Headers:
    - X-Session-Id: Optional session identifier for conversation context
    
    Response:
    - response: Agent response text
    - session_id: Session identifier for conversation continuity
    - timestamp: Response timestamp in ISO format
    """
    
    logger.info(f"Processing chat request: {json.dumps(event, default=str)}")
    
    try:
        # Handle OPTIONS request for CORS
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': create_cors_headers(),
                'body': ''
            }
        
        # Validate HTTP method
        if event.get('httpMethod') != 'POST':
            return create_error_response(
                405,
                'Method Not Allowed',
                'Only POST method is allowed for this endpoint'
            )
        
        # Validate request body
        message, body = validate_request_body(event.get('body'))
        
        logger.info(f"Received message: {message[:100]}...")
        
        # Extract session ID from headers
        session_id = extract_session_id(event.get('headers'))
        
        # Get orchestrator ARN from environment
        orchestrator_arn = os.environ.get('ORCHESTRATOR_ARN')
        if not orchestrator_arn:
            logger.error("ORCHESTRATOR_ARN environment variable not set")
            return create_error_response(
                500,
                'Configuration Error',
                'Agent runtime configuration is missing'
            )
        
        logger.info(f"Using orchestrator ARN: {orchestrator_arn}")
        
        # Invoke the agent runtime
        response = invoke_agent_runtime(orchestrator_arn, session_id, message)
        
        # Process the streaming response
        agent_response = process_streaming_response(response)
        
        logger.info(f"Agent response length: {len(agent_response)} characters")
        
        # Prepare success response
        response_body = {
            'response': agent_response,
            'session_id': session_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        logger.info("Chat request completed successfully")
        
        return {
            'statusCode': 200,
            'headers': create_cors_headers(),
            'body': json.dumps(response_body, default=decimal_default)
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return create_error_response(400, 'Validation Error', str(e))
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"AWS service error: {error_code} - {error_message}")
        
        if error_code == 'ResourceNotFoundException':
            return create_error_response(
                404,
                'Agent Not Found',
                'The orchestrator agent is not available'
            )
        elif error_code == 'AccessDeniedException':
            return create_error_response(
                403,
                'Access Denied',
                'Insufficient permissions to access the agent'
            )
        elif error_code == 'ThrottlingException':
            return create_error_response(
                429,
                'Too Many Requests',
                'Agent service is currently busy, please try again'
            )
        elif error_code == 'ServiceQuotaExceededException':
            return create_error_response(
                503,
                'Service Unavailable',
                'Agent service quota exceeded'
            )
        else:
            return create_error_response(
                500,
                'Agent Service Error',
                'Unable to communicate with the agent',
                {'code': error_code}
            )
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return create_error_response(
            500,
            'Internal Server Error',
            'An unexpected error occurred'
        )