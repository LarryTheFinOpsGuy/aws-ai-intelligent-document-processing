"""
Lambda function for Processing Rules API.
Provides REST API wrapper around S3 Vector Lambda for managing document processing rules
and S3 Bucket Lambda for instructions management.
"""
import json
import os
import boto3
import base64
import logging
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_client = boto3.client('lambda')
S3_VECTOR_LAMBDA = os.environ.get('S3_VECTOR_LAMBDA_NAME')
S3_BUCKET_LAMBDA = os.environ.get('S3_BUCKET_LAMBDA_NAME')

def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create API Gateway response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS'
        },
        'body': json.dumps(body)
    }

def invoke_s3_vector_lambda(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke S3 Vector Lambda with MCP context."""
    client_context = {
        "custom": {
            "bedrockAgentCoreToolName": f"agenticidp-s3-vector-target___{tool_name}"
        }
    }
    
    response = lambda_client.invoke(
        FunctionName=S3_VECTOR_LAMBDA,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload),
        ClientContext=base64.b64encode(json.dumps(client_context).encode()).decode()
    )
    
    result = json.loads(response['Payload'].read())
    return result

def invoke_s3_bucket_lambda(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke S3 Bucket Lambda with MCP context."""
    client_context = {
        "custom": {
            "bedrockAgentCoreToolName": f"agenticidp-s3-bucket-target___{tool_name}"
        }
    }
    
    response = lambda_client.invoke(
        FunctionName=S3_BUCKET_LAMBDA,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload),
        ClientContext=base64.b64encode(json.dumps(client_context).encode()).decode()
    )
    
    result = json.loads(response['Payload'].read())
    
    # Check for S3 errors and handle gracefully
    if 'errorMessage' in result:
        error_msg = result['errorMessage']
        if 'NoSuchKey' in error_msg:
            return {"error": "File not found", "message": f"The requested file does not exist"}
        else:
            return {"error": f"S3 error: {error_msg}"}
    
    # Transform response format from file_content to content for UI compatibility
    if 'file_content' in result:
        file_content = result['file_content']
        file_key = payload.get('file_key', '')
        
        # Decode base64 content for text files
        if file_key.endswith('.txt') or file_key.endswith('.json'):
            try:
                decoded_content = base64.b64decode(file_content).decode('utf-8')
                result['content'] = decoded_content
            except Exception as e:
                logger.error(f"Error decoding content: {e}")
                result['content'] = file_content
        else:
            result['content'] = file_content
        
        # Remove the original file_content key
        del result['file_content']
    
    return result

def invoke_s3_vector_lambda(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke S3 Vector Lambda with MCP context."""
    client_context = {
        "custom": {
            "bedrockAgentCoreToolName": f"agenticidp-s3-vector-target___{tool_name}"
        }
    }
    
    response = lambda_client.invoke(
        FunctionName=S3_VECTOR_LAMBDA,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload),
        ClientContext=base64.b64encode(json.dumps(client_context).encode()).decode()
    )
    
    result = json.loads(response['Payload'].read())
    return result

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Handle Processing Rules API requests."""
    try:
        logger.info(f"Event: {json.dumps(event)}")
        
        http_method = event.get('httpMethod')
        path = event.get('path', '')
        path_parameters = event.get('pathParameters') or {}
        query_parameters = event.get('queryStringParameters') or {}
        
        # GET /api/processing-rules - List all rules
        if http_method == 'GET' and path.endswith('/processing-rules'):
            max_results = int(query_parameters.get('limit', 100))
            next_token = query_parameters.get('nextToken')
            
            payload = {
                'max_results': max_results,
                'return_metadata': True
            }
            if next_token:
                payload['next_token'] = next_token
            
            result = invoke_s3_vector_lambda('list_documents', payload)
            
            if result.get('statusCode') == 200:
                body = json.loads(result['body'])
                return create_response(200, body)
            else:
                return create_response(500, {'error': 'Failed to list processing rules'})
        
        # POST /api/processing-rules/search - Search by sender name
        elif http_method == 'POST' and path.endswith('/search'):
            body = json.loads(event.get('body', '{}'))
            sender_name = body.get('sender_name', '')
            document_type = body.get('document_type')
            status = body.get('status')
            
            if not sender_name:
                return create_response(400, {'error': 'sender_name is required'})
            
            payload = {
                'query_text': sender_name,
                'max_results': 10,
                'similarity_threshold': 0.5
            }
            
            if document_type:
                payload['document_type'] = document_type
            if status:
                payload['status'] = status
            
            result = invoke_s3_vector_lambda('search_documents', payload)
            
            if result.get('statusCode') == 200:
                body = json.loads(result['body'])
                return create_response(200, body)
            else:
                return create_response(500, {'error': 'Failed to search processing rules'})
        
        # GET /api/processing-rules/{id} - Get single rule
        elif http_method == 'GET' and path_parameters and path_parameters.get('id'):
            document_id = path_parameters.get('id')
            
            if not document_id:
                return create_response(400, {'error': 'document_id is required'})
            
            payload = {'document_id': document_id}
            result = invoke_s3_vector_lambda('get_document', payload)
            
            if result.get('statusCode') == 200:
                body = json.loads(result['body'])
                return create_response(200, body)
            else:
                return create_response(404, {'error': 'Processing rule not found'})
        
        # PATCH /api/processing-rules/{id} - Update rule status
        elif http_method == 'PATCH' and path_parameters and path_parameters.get('id'):
            document_id = path_parameters.get('id')
            body = json.loads(event.get('body', '{}'))
            status = body.get('status')
            
            if not document_id:
                return create_response(400, {'error': 'document_id is required'})
            
            if not status or status not in ['ACTIVE', 'PENDING REVIEW', 'ARCHIVED']:
                return create_response(400, {'error': 'status must be ACTIVE, PENDING REVIEW, or ARCHIVED'})
            
            payload = {
                'document_id': document_id,
                'status': status
            }
            
            result = invoke_s3_vector_lambda('update_document', payload)
            
            if result.get('statusCode') == 200:
                body = json.loads(result['body'])
                return create_response(200, body)
            else:
                return create_response(500, {'error': 'Failed to update processing rule'})
        
        # POST /api/processing-rules/s3-bucket - Instructions management
        elif http_method == 'POST' and '/s3-bucket' in path:
            body = json.loads(event.get('body', '{}'))
            tool_name = body.get('tool_name', 'download_file')
            
            # Remove tool_name from payload to avoid conflicts
            payload = {k: v for k, v in body.items() if k != 'tool_name'}
            
            result = invoke_s3_bucket_lambda(tool_name, payload)
            
            if result.get('statusCode') == 200:
                response_body = json.loads(result['body'])
                
                # Transform response for instructions editor compatibility
                if tool_name == 'download_file' and 'file_content' in response_body:
                    # Decode base64 content if needed
                    file_content = response_body['file_content']
                    if response_body.get('content_encoding') != 'base64':
                        try:
                            import base64
                            file_content = base64.b64decode(file_content).decode('utf-8')
                        except:
                            pass  # Content might already be decoded
                    
                    # Return in expected format
                    return create_response(200, {'content': file_content})
                
                return create_response(200, response_body)
            else:
                return create_response(500, {'error': 'Failed to execute S3 bucket operation'})
        
        # GET /api/processing-rules/{document_id} - Get processing rule by document ID
        elif http_method == 'GET' and '/processing-rules/' in path:
            # Extract document ID from path
            path_parts = path.split('/')
            if len(path_parts) >= 4:
                document_id = path_parts[-1]  # Last part of the path
                
                payload = {
                    'document_id': document_id
                }
                
                result = invoke_s3_vector_lambda('get_document', payload)
                
                if result.get('statusCode') == 200:
                    body = json.loads(result['body'])
                    return create_response(200, body)
                else:
                    return create_response(404, {'error': 'Processing rule not found'})
            else:
                return create_response(400, {'error': 'Invalid document ID in path'})
        
        else:
            return create_response(404, {'error': 'Not found'})
            
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return create_response(500, {'error': str(e)})
