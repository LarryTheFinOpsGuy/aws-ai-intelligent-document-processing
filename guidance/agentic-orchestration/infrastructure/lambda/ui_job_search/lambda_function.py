import json
import boto3
import os
from typing import Dict, Any

dynamodb = boto3.resource('dynamodb')
PROCESSING_JOBS_TABLE = os.environ['PROCESSING_JOBS_TABLE']

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,OPTIONS'
}

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Search for a job by job_id"""
    try:
        # Get job_id from query parameters
        job_id = event.get('queryStringParameters', {}).get('job_id') if event.get('queryStringParameters') else None
        
        if not job_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Missing job_id query parameter"})
            }
        
        # Get job from DynamoDB
        table = dynamodb.Table(PROCESSING_JOBS_TABLE)
        response = table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in response:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": f"Job not found: {job_id}"})
            }
        
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({
                "job": response['Item']
            }, default=str)
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)})
        }
