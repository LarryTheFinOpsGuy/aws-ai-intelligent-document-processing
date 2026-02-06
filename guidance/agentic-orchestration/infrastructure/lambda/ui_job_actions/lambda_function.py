#!/usr/bin/env python3
"""
Lambda function for UI job actions API.
Queries DynamoDB processing-actions table for a specific job and returns detailed action history.
Includes job details from processing-jobs table with comprehensive error handling.
"""

import json
import os
import boto3
import logging
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

# Import common utilities
from common.dynamodb_jobs import DynamoDBJobsClient

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
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Session-Id',
        'Access-Control-Allow-Methods': 'GET,OPTIONS'
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


def validate_job_id(job_id):
    """Validate job_id parameter."""
    if not job_id:
        raise ValueError("job_id is required in the path")
    
    if not isinstance(job_id, str):
        raise ValueError("job_id must be a string")
    
    # Basic format validation - should be UUID-like or reasonable identifier
    if len(job_id.strip()) == 0:
        raise ValueError("job_id cannot be empty")
    
    return job_id.strip()


def format_job_details(job):
    """Format job details for API response."""
    return {
        'job_id': job.get('job_id', ''),
        's3_uri': job.get('s3_uri', ''),
        'sender_name': job.get('sender_name', 'Unknown'),
        'status': job.get('status', 'unknown'),
        'created_at': job.get('created_at', ''),
        'updated_at': job.get('updated_at', ''),
        'doc_type': job.get('doc_type', ''),
        'current_step': job.get('current_step', '')
    }


def format_action_response(action):
    """Format a single action for API response."""
    return {
        'job_id': action.get('job_id', ''),
        'started_at': action.get('started_at', ''),
        'agent': action.get('agent', 'unknown'),
        'action_type': action.get('action_type', 'unknown'),
        'status': action.get('status', 'unknown'),
        'completed_at': action.get('completed_at', ''),
        'result': action.get('result'),
        'error_message': action.get('error_message', '')
    }


def get_job_actions(actions_table, job_id):
    """Query processing-actions table for job actions."""
    try:
        logger.info(f"Querying actions for job_id: {job_id}")
        
        response = actions_table.query(
            KeyConditionExpression=Key('job_id').eq(job_id)
        )
        
        actions = response.get('Items', [])
        logger.info(f"Retrieved {len(actions)} actions for job {job_id}")
        
        # Sort actions by started_at timestamp
        actions.sort(key=lambda x: x.get('started_at', ''))
        
        return actions
        
    except ClientError as e:
        logger.warning(f"Error querying actions table: {e}")
        raise


def lambda_handler(event, context):
    """
    Handle GET /api/jobs/{job_id}/actions request with API Gateway proxy integration.
    Returns detailed job history with all processing actions and job details.
    
    Path Parameters:
    - job_id: Unique identifier for the job
    
    Response:
    - job_id: The requested job ID
    - job_details: Complete job information from processing-jobs table
    - actions: Array of processing actions with agent, action_type, status, timestamps
    - total_actions: Number of actions returned
    """
    
    logger.info(f"Processing job actions request: {json.dumps(event, default=str)}")
    
    try:
        # Handle OPTIONS request for CORS
        if event.get('httpMethod') == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': create_cors_headers(),
                'body': ''
            }
        
        # Validate HTTP method
        if event.get('httpMethod') != 'GET':
            return create_error_response(
                405,
                'Method Not Allowed',
                'Only GET method is allowed for this endpoint'
            )
        
        # Validate path parameters
        path_params = event.get('pathParameters') or {}
        job_id = validate_job_id(path_params.get('job_id'))
        
        logger.info(f"Processing request for job_id: {job_id}")
        
        # Initialize DynamoDB resources
        jobs_table_name = os.environ['PROCESSING_JOBS_TABLE']
        actions_table_name = os.environ['PROCESSING_ACTIONS_TABLE']
        region = os.environ.get('AWS_REGION', 'us-west-2')
        
        logger.info(f"Using tables - jobs: {jobs_table_name}, actions: {actions_table_name}")
        
        # Initialize DynamoDB client for jobs
        jobs_client = DynamoDBJobsClient(jobs_table_name, region)
        
        # Initialize DynamoDB resource for actions (direct access for query)
        dynamodb = boto3.resource('dynamodb', region_name=region)
        actions_table = dynamodb.Table(actions_table_name)
        
        # Get job details
        logger.info(f"Retrieving job details for job_id: {job_id}")
        job_details = jobs_client.get_job(job_id)
        
        if not job_details:
            logger.warning(f"Job not found: {job_id}")
            return create_error_response(
                404, 
                'Job Not Found', 
                f'Job with ID {job_id} does not exist'
            )
        
        logger.info(f"Found job: {job_details.get('status', 'unknown')} status")
        
        # Get job actions
        actions = get_job_actions(actions_table, job_id)
        
        # Format response data
        formatted_job = format_job_details(job_details)
        formatted_actions = [format_action_response(action) for action in actions]
        
        # Prepare response
        response_body = {
            'job_id': job_id,
            'job_details': formatted_job,
            'actions': formatted_actions,
            'total_actions': len(formatted_actions)
        }
        
        logger.info(f"Returning job details and {len(formatted_actions)} actions for job {job_id}")
        
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
        logger.error(f"DynamoDB error: {error_code} - {error_message}")
        
        if error_code == 'ResourceNotFoundException':
            return create_error_response(404, 'Resource Not Found', 'Required table not found')
        elif error_code == 'AccessDeniedException':
            return create_error_response(403, 'Access Denied', 'Insufficient permissions to access job data')
        else:
            return create_error_response(500, 'Database Error', 'Unable to retrieve job actions', {'code': error_code})
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return create_error_response(500, 'Internal Server Error', 'An unexpected error occurred')