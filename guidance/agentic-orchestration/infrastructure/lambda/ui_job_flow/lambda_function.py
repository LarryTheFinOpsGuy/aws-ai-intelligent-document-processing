import json
import boto3
import os
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
PROCESSING_JOBS_TABLE = os.environ['PROCESSING_JOBS_TABLE']
PROCESSING_ACTIONS_TABLE = os.environ['PROCESSING_ACTIONS_TABLE']

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,OPTIONS'
}

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Get job execution flow for UI visualization"""
    try:
        # Extract job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')
        if not job_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Missing job_id"})
            }
        
        # Get job details
        jobs_table = dynamodb.Table(PROCESSING_JOBS_TABLE)
        job_response = jobs_table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in job_response:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": f"Job not found: {job_id}"})
            }
        
        job = job_response['Item']
        
        # Get all actions for the job
        actions_table = dynamodb.Table(PROCESSING_ACTIONS_TABLE)
        actions_response = actions_table.query(
            KeyConditionExpression='job_id = :job_id',
            ExpressionAttributeValues={':job_id': job_id},
            ScanIndexForward=True  # Chronological order
        )
        
        actions = actions_response['Items']
        
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "job": job,
                "actions": actions
            }, default=str)
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)})
        }
