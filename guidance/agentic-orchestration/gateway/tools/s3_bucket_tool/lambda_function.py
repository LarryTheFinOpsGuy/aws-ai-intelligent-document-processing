import sys
import os
import logging
import traceback
import json
import boto3
import base64
from typing import Dict, Any
from urllib.parse import urlparse
from response_utils import create_error_response, create_success_response, parse_lambda_event
from auth_utils import log_request

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize S3 client
s3_client = boto3.client('s3')

# Configuration
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET')

def normalize_file_key(file_key: str) -> str:
    """Extract S3 key from full S3 URI if needed."""
    if file_key.startswith('s3://'):
        return urlparse(file_key).path.lstrip('/')
    return file_key

def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)).decode() == s
    except Exception:
        return False

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main Lambda handler for S3 bucket operations."""
    try:
        log_request(event, context)
        
        # Get tool name from context
        tool_name = None
        
        # Check if called via Bedrock Agent Core
        if hasattr(context, 'client_context') and context.client_context and hasattr(context.client_context, 'custom'):
            tool_name = context.client_context.custom['bedrockAgentCoreToolName']
            logger.info(f"Original toolName: {tool_name}")
            
            # Remove target prefix if present
            delimiter = "___"
            if delimiter in tool_name:
                tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
            print(f"Converted toolName: {tool_name}")
        
        # Default to download_file if no tool_name specified (for backward compatibility)
        if not tool_name:
            tool_name = 'download_file'
            logger.info("No tool_name specified, defaulting to download_file")
        
        # Use event as parameters
        parameters = event
        
        if tool_name == 'upload_file':
            return upload_file(parameters)
        elif tool_name == 'download_file':
            return download_file(parameters)
        elif tool_name == 'list_files':
            return list_files(parameters)
        elif tool_name == 'delete_file':
            return delete_file(parameters)
        elif tool_name == 'get_file_info':
            return get_file_info(parameters)
        else:
            return create_error_response(f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Tool execution failed: {str(e)}")

def upload_file(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Upload file to S3 bucket."""
    try:
        file_key = normalize_file_key(parameters.get('file_key'))
        file_content = parameters.get('file_content')
        content_type = parameters.get('content_type', 'text/plain')
        metadata = parameters.get('metadata', {})
        
        if not all([file_key, file_content]):
            return create_error_response("Missing required parameters: file_key, file_content")
        
        # Handle content based on encoding
        if isinstance(file_content, str) and is_base64(file_content):
            file_bytes = base64.b64decode(file_content)
        else:
            file_bytes = file_content.encode('utf-8') if isinstance(file_content, str) else file_content
        
        # Upload to S3
        s3_client.put_object(
            Bucket=DOCUMENT_BUCKET,
            Key=file_key,
            Body=file_bytes,
            ContentType=content_type,
            Metadata=metadata
        )
        
        s3_uri = f"s3://{DOCUMENT_BUCKET}/{file_key}"
        
        result = {
            "file_key": file_key,
            "s3_uri": s3_uri,
            "bucket": DOCUMENT_BUCKET,
            "size_bytes": len(file_bytes),
            "content_type": content_type,
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error uploading file: {str(e)}")

def download_file(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Download file from S3 bucket."""
    try:
        file_key = normalize_file_key(parameters.get('file_key'))
        return_base64 = parameters.get('return_base64', True)
        
        if not file_key:
            return create_error_response("Missing required parameter: file_key")
        
        # Download from S3
        response = s3_client.get_object(Bucket=DOCUMENT_BUCKET, Key=file_key)
        file_content = response['Body'].read()
        
        # Get metadata
        metadata = response.get('Metadata', {})
        content_type = response.get('ContentType', 'application/octet-stream')
        last_modified = response.get('LastModified')
        
        result = {
            "file_key": file_key,
            "s3_uri": f"s3://{DOCUMENT_BUCKET}/{file_key}",
            "bucket": DOCUMENT_BUCKET,
            "size_bytes": len(file_content),
            "content_type": content_type,
            "last_modified": last_modified.isoformat() if last_modified else None,
            "metadata": metadata,
            "success": True
        }
        
        if return_base64:
            result["file_content"] = base64.b64encode(file_content).decode('utf-8')
        else:
            # For text files, try to decode as UTF-8
            try:
                result["file_content"] = file_content.decode('utf-8')
            except UnicodeDecodeError:
                result["file_content"] = base64.b64encode(file_content).decode('utf-8')
                result["content_encoding"] = "base64"
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if "NoSuchKey" in str(e):
            return create_error_response(f"File not found: {file_key}")
        return create_error_response(f"Error downloading file: {str(e)}")

def list_files(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """List files in S3 bucket."""
    try:
        prefix = parameters.get('prefix', '')
        max_keys = parameters.get('max_keys', 100)
        continuation_token = parameters.get('continuation_token')
        
        # List objects
        list_params = {
            'Bucket': DOCUMENT_BUCKET,
            'Prefix': prefix,
            'MaxKeys': min(max_keys, 1000)  # AWS limit
        }
        
        if continuation_token:
            list_params['ContinuationToken'] = continuation_token
        
        response = s3_client.list_objects_v2(**list_params)
        
        files = []
        for obj in response.get('Contents', []):
            files.append({
                "file_key": obj['Key'],
                "s3_uri": f"s3://{DOCUMENT_BUCKET}/{obj['Key']}",
                "size_bytes": obj['Size'],
                "last_modified": obj['LastModified'].isoformat(),
                "etag": obj['ETag'].strip('"')
            })
        
        result = {
            "files": files,
            "total_files": len(files),
            "prefix": prefix,
            "bucket": DOCUMENT_BUCKET,
            "is_truncated": response.get('IsTruncated', False),
            "success": True
        }
        
        if response.get('NextContinuationToken'):
            result["next_continuation_token"] = response['NextContinuationToken']
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error listing files: {str(e)}")

def delete_file(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Delete file from S3 bucket."""
    try:
        file_key = normalize_file_key(parameters.get('file_key'))
        
        if not file_key:
            return create_error_response("Missing required parameter: file_key")
        
        # Delete from S3
        s3_client.delete_object(Bucket=DOCUMENT_BUCKET, Key=file_key)
        
        result = {
            "file_key": file_key,
            "s3_uri": f"s3://{DOCUMENT_BUCKET}/{file_key}",
            "bucket": DOCUMENT_BUCKET,
            "deleted": True,
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error deleting file: {str(e)}")

def get_file_info(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get file metadata without downloading content."""
    try:
        file_key = normalize_file_key(parameters.get('file_key'))
        
        if not file_key:
            return create_error_response("Missing required parameter: file_key")
        
        # Get object metadata
        response = s3_client.head_object(Bucket=DOCUMENT_BUCKET, Key=file_key)
        
        result = {
            "file_key": file_key,
            "s3_uri": f"s3://{DOCUMENT_BUCKET}/{file_key}",
            "bucket": DOCUMENT_BUCKET,
            "size_bytes": response['ContentLength'],
            "content_type": response.get('ContentType', 'application/octet-stream'),
            "last_modified": response['LastModified'].isoformat(),
            "etag": response['ETag'].strip('"'),
            "metadata": response.get('Metadata', {}),
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if "NoSuchKey" in str(e):
            return create_error_response(f"File not found: {file_key}")
        return create_error_response(f"Error getting file info: {str(e)}")
