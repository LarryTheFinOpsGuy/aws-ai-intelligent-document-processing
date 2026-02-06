import json
import logging
import traceback
import boto3
import os
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Table names from environment variables
PROCESSING_JOBS_TABLE = os.environ.get('PROCESSING_JOBS_TABLE', 'processing-jobs')
PROCESSING_ACTIONS_TABLE = os.environ.get('PROCESSING_ACTIONS_TABLE', 'processing-actions')

def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create success response"""
    return {
        "statusCode": 200,
        "body": json.dumps(data, default=str)
    }

def create_error_response(error_message: str) -> Dict[str, Any]:
    """Create error response"""
    return {
        "statusCode": 400,
        "body": json.dumps({"error": error_message, "success": False})
    }

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main Lambda handler for DynamoDB job operations"""
    try:
        # Get tool name from context
        tool_name = context.client_context.custom['bedrockAgentCoreToolName']
        
        # Remove target prefix if present
        delimiter = "___"
        if delimiter in tool_name:
            tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
        
        # Use event as parameters
        parameters = event
        
        if tool_name == 'update_job':
            return update_job(parameters)
        elif tool_name == 'get_job':
            return get_job(parameters)
        elif tool_name == 'get_job_status':
            return get_job_status(parameters)
        elif tool_name == 'get_job_actions':
            return get_job_actions(parameters)
        elif tool_name == 'get_latest_action':
            return get_latest_action(parameters)
        elif tool_name == 'get_recent_jobs':
            return get_recent_jobs(parameters)
        else:
            return create_error_response(f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Tool execution failed: {str(e)}")

def update_job(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Update job fields"""
    try:
        job_id = parameters.get('job_id')
        if not job_id:
            return create_error_response("Missing required parameter: job_id")
        
        table = dynamodb.Table(PROCESSING_JOBS_TABLE)
        
        # Build update expression
        update_expression = "SET updated_at = :updated_at"
        expression_values = {":updated_at": datetime.utcnow().isoformat() + 'Z'}
        expression_names = {}
        
        # Add fields to update
        for field in ['doc_type', 'sender_name', 'markdown_s3_uri', 'match_doc_id', 'instructions_s3_uri', 'extracted_data_s3_uri', 'status']:
            if field in parameters:
                if field == 'status':
                    # Handle reserved keyword
                    update_expression += f", #status = :status"
                    expression_names['#status'] = 'status'
                    expression_values[':status'] = parameters[field]
                else:
                    update_expression += f", {field} = :{field}"
                    expression_values[f":{field}"] = parameters[field]
        
        update_params = {
            'Key': {'job_id': job_id},
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': expression_values,
            'ReturnValues': 'ALL_NEW'
        }
        
        if expression_names:
            update_params['ExpressionAttributeNames'] = expression_names
        
        response = table.update_item(**update_params)
        
        return create_success_response({
            "job": response['Attributes'],
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error updating job: {str(e)}")
        return create_error_response(f"Error updating job: {str(e)}")

def get_job(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get job by job_id"""
    try:
        job_id = parameters.get('job_id')
        if not job_id:
            return create_error_response("Missing required parameter: job_id")
        
        table = dynamodb.Table(PROCESSING_JOBS_TABLE)
        response = table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in response:
            return create_error_response(f"Job not found: {job_id}")
        
        return create_success_response({
            "job": response['Item'],
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting job: {str(e)}")
        return create_error_response(f"Error getting job: {str(e)}")

def get_job_status(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get job status from latest action"""
    try:
        job_id = parameters.get('job_id')
        if not job_id:
            return create_error_response("Missing required parameter: job_id")
        
        table = dynamodb.Table(PROCESSING_ACTIONS_TABLE)
        response = table.query(
            KeyConditionExpression='job_id = :job_id',
            ExpressionAttributeValues={':job_id': job_id},
            ScanIndexForward=False,  # Descending order
            Limit=1
        )
        
        if not response['Items']:
            return create_success_response({
                "status": "pending",
                "success": True
            })
        
        latest_action = response['Items'][0]
        
        # Determine status from latest action
        if not latest_action.get('completed_at'):
            status = "processing"
        elif latest_action.get('success', True):
            status = "completed"
        else:
            status = "failed"
        
        return create_success_response({
            "status": status,
            "latest_action": latest_action,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return create_error_response(f"Error getting job status: {str(e)}")

def get_job_actions(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get all actions for a job, optionally filtered by agent"""
    try:
        job_id = parameters.get('job_id')
        if not job_id:
            return create_error_response("Missing required parameter: job_id")
        
        agent = parameters.get('agent')
        limit = parameters.get('limit', 100)
        
        table = dynamodb.Table(PROCESSING_ACTIONS_TABLE)
        
        if agent:
            # Use GSI to filter by agent
            response = table.query(
                IndexName='agent-started_at-index',
                KeyConditionExpression='agent = :agent',
                FilterExpression='job_id = :job_id',
                ExpressionAttributeValues={
                    ':agent': agent,
                    ':job_id': job_id
                },
                ScanIndexForward=True,  # Ascending order (chronological)
                Limit=limit
            )
        else:
            # Query all actions for the job
            response = table.query(
                KeyConditionExpression='job_id = :job_id',
                ExpressionAttributeValues={':job_id': job_id},
                ScanIndexForward=True,  # Ascending order (chronological)
                Limit=limit
            )
        
        return create_success_response({
            "actions": response['Items'],
            "count": len(response['Items']),
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting job actions: {str(e)}")
        return create_error_response(f"Error getting job actions: {str(e)}")

def get_recent_jobs(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent jobs by status, ordered by created_at (newest first)"""
    try:
        status = parameters.get('status', 'CREATED')  # Default to 'CREATED'
        limit = min(parameters.get('limit', 50), 50)  # Max 50 jobs
        
        table = dynamodb.Table(PROCESSING_JOBS_TABLE)
        
        # Query GSI by status + created_at
        response = table.query(
            IndexName='status-created_at-index',
            KeyConditionExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': status},
            ScanIndexForward=False,  # Descending order (newest first)
            Limit=limit
        )
        
        return create_success_response({
            "jobs": response['Items'],
            "count": len(response['Items']),
            "status_filter": status,
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting recent jobs: {str(e)}")
        return create_error_response(f"Error getting recent jobs: {str(e)}")

def get_latest_action(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get latest action for a job"""
    try:
        job_id = parameters.get('job_id')
        if not job_id:
            return create_error_response("Missing required parameter: job_id")
        
        table = dynamodb.Table(PROCESSING_ACTIONS_TABLE)
        response = table.query(
            KeyConditionExpression='job_id = :job_id',
            ExpressionAttributeValues={':job_id': job_id},
            ScanIndexForward=False,  # Descending order
            Limit=1
        )
        
        if not response['Items']:
            return create_error_response(f"No actions found for job: {job_id}")
        
        return create_success_response({
            "action": response['Items'][0],
            "success": True
        })
        
    except Exception as e:
        logger.error(f"Error getting latest action: {str(e)}")
        return create_error_response(f"Error getting latest action: {str(e)}")
