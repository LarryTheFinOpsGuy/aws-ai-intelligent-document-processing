"""Processing actions utilities for multi-agent workflow."""
import boto3
import os
from datetime import datetime
from typing import Optional

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
PROCESSING_ACTIONS_TABLE = os.environ.get('PROCESSING_ACTIONS_TABLE', 'processing-actions')

def create_action_start(job_id: str, agent: str) -> str:
    """Create ProcessingActions record with started_at timestamp.
    
    Args:
        job_id: Job identifier
        agent: Agent name performing the action
        
    Returns:
        started_at timestamp (ISO format)
    """
    try:
        table = dynamodb.Table(PROCESSING_ACTIONS_TABLE)
        started_at = datetime.utcnow().isoformat() + 'Z'
        
        item = {
            'job_id': job_id,
            'started_at': started_at,
            'agent': agent
        }
        
        table.put_item(Item=item)
        return started_at
    except Exception as e:
        print(f"Error creating action start record: {e}")
        print(f"Table: {PROCESSING_ACTIONS_TABLE}")
        raise

def update_action_complete(job_id: str, started_at: str, result: str, success: bool = True) -> None:
    """Update ProcessingActions record with completion details.
    
    Args:
        job_id: Job identifier
        started_at: Original start timestamp (sort key)
        result: Action result or error message
        success: Whether action completed successfully
    """
    try:
        table = dynamodb.Table(PROCESSING_ACTIONS_TABLE)
        completed_at = datetime.utcnow().isoformat() + 'Z'
        
        table.update_item(
            Key={
                'job_id': job_id,
                'started_at': started_at
            },
            UpdateExpression='SET completed_at = :completed_at, #result = :result, success = :success',
            ExpressionAttributeNames={'#result': 'result'},
            ExpressionAttributeValues={
                ':completed_at': completed_at,
                ':result': result,
                ':success': success
            }
        )
    except Exception as e:
        print(f"Error updating action completion: {e}")
        print(f"Table: {PROCESSING_ACTIONS_TABLE}")
        raise
