#!/usr/bin/env python3
"""
Lambda function for UI jobs listing API.
Queries DynamoDB processing-jobs table and returns recent jobs with pagination and sorting.
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
    # Updated: 2025-12-23 to support CloudFront origins
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


def validate_query_parameters(query_params):
    """Validate and parse query parameters."""
    try:
        limit = int(query_params.get('limit', 10))
        # Enforce reasonable limits
        if limit < 1:
            limit = 1
        elif limit > 100:
            limit = 100
            
        # Get status filter (default to COMPLETED)
        status = query_params.get('status', 'COMPLETED')
        valid_statuses = ['CREATED', 'PROCESSING', 'COMPLETED', 'FAILED']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
        # Get pagination token if provided
        last_evaluated_key = query_params.get('last_key')
        if last_evaluated_key:
            try:
                last_evaluated_key = json.loads(last_evaluated_key)
            except json.JSONDecodeError:
                raise ValueError("Invalid last_key format")
        
        return limit, status, last_evaluated_key
        
    except ValueError as e:
        raise ValueError(f"Invalid query parameters: {str(e)}")





def format_job_response(job):
    """Format a single job for API response."""
    return {
        'job_id': job.get('job_id', ''),
        's3_uri': job.get('s3_uri', ''),
        'sender_name': job.get('sender_name', 'Unknown'),
        'status': job.get('status', 'unknown'),
        'created_at': job.get('created_at', ''),
        'doc_type': job.get('doc_type', '')
    }


def lambda_handler(event, context):
    """
    Handle GET /api/jobs request with API Gateway proxy integration.
    Returns list of recent processing jobs with pagination and sorting.
    
    Query Parameters:
    - limit: Number of jobs to return (1-100, default: 10)
    - status: Status filter (CREATED, PROCESSING, COMPLETED, FAILED, default: COMPLETED)
    - last_key: Pagination token for next page (JSON encoded)
    
    Response:
    - jobs: Array of job objects
    - total_count: Number of jobs returned
    - has_more: Boolean indicating if more jobs are available
    - next_key: Pagination token for next page (if has_more is true)
    - status_counts: Object with counts for each status
    """
    
    logger.info(f"Processing jobs listing request: {json.dumps(event, default=str)}")
    
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
        
        # Validate query parameters
        query_params = event.get('queryStringParameters') or {}
        limit, status, last_evaluated_key = validate_query_parameters(query_params)
        
        logger.info(f"Query parameters - limit: {limit}, status: {status}, last_key provided: {last_evaluated_key is not None}")
        
        # Initialize DynamoDB client
        table_name = os.environ['PROCESSING_JOBS_TABLE']
        jobs_client = DynamoDBJobsClient(table_name)
        
        logger.info(f"Querying table: {table_name} for status: {status}")
        
        # Query jobs by status using GSI
        result = jobs_client.list_jobs_by_status(status, limit, last_evaluated_key)
        jobs = result['jobs']
        
        # Get status counts for selector
        status_counts = jobs_client.get_status_counts()
        
        logger.info(f"Retrieved {len(jobs)} jobs with status {status}, status counts: {status_counts}")
        
        # Format jobs for response
        formatted_jobs = [format_job_response(job) for job in jobs]
        
        # Prepare response
        response_body = {
            'jobs': formatted_jobs,
            'total_count': len(formatted_jobs),
            'has_more': result['has_more'],
            'status_counts': status_counts
        }
        
        # Include pagination token if there are more results
        if result['last_evaluated_key']:
            response_body['next_key'] = json.dumps(result['last_evaluated_key'], default=decimal_default)
        
        logger.info(f"Returning {len(formatted_jobs)} jobs, has_more: {response_body['has_more']}")
        
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
            return create_error_response(404, 'Resource Not Found', 'Jobs table not found')
        elif error_code == 'AccessDeniedException':
            return create_error_response(403, 'Access Denied', 'Insufficient permissions to access jobs')
        else:
            return create_error_response(500, 'Database Error', 'Unable to retrieve jobs', {'code': error_code})
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return create_error_response(500, 'Internal Server Error', 'An unexpected error occurred')