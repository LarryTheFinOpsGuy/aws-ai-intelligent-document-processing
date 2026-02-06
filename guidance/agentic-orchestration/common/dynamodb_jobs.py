import boto3
import json
import uuid
import time
from typing import Dict, Any, Optional

class DynamoDBJobsClient:
    """Shared utility for DynamoDB job operations."""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self._dynamodb = None
        self._table = None
    
    @property
    def dynamodb(self):
        if self._dynamodb is None:
            self._dynamodb = boto3.resource('dynamodb')
        return self._dynamodb
    
    @property
    def table(self):
        if self._table is None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table
    
    @staticmethod
    def generate_job_id() -> str:
        """Generate unique job ID."""
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_timestamp() -> int:
        """Generate timestamp in milliseconds."""
        return int(time.time() * 1000)
    
    def create_job(self, job_id: str, s3_uri: str, status: str = "started") -> Dict[str, Any]:
        """Create new job record."""
        timestamp = self.generate_timestamp()
        
        # Create initial shared state as JSON string
        initial_shared_state = {}
        
        item = {
            'job_id': job_id,
            's3_uri': s3_uri,
            'status': status,
            'created_at': timestamp,
            'updated_at': timestamp,
            'agent_shared_state': json.dumps(initial_shared_state)
        }
        
        self.table.put_item(Item=item)
        return item
    
    def update_job(self, job_id: str, **kwargs) -> Dict[str, Any]:
        """Update job with provided fields."""
        update_expr = "SET updated_at = :updated"
        expr_values = {':updated': self.generate_timestamp()}
        expr_names = {}
        
        # Handle status
        if 'status' in kwargs:
            update_expr += ", #status = :status"
            expr_values[':status'] = kwargs['status']
            expr_names['#status'] = 'status'
        
        # Handle doc_type and sender
        special_fields = {'status', 'shared_state'}
        safe_fields = {'doc_type', 'sender', 'agent_name', 'error_message', 'extracted_data_uri', 'match_doc_id'}
        
        for field, value in kwargs.items():
            if field not in special_fields:
                if field in safe_fields or field.endswith('_uri'):
                    if isinstance(value, str):
                        update_expr += f", {field} = :{field}"
                        expr_values[f':{field}'] = value
                    else:
                        print(f"Warning: Skipping field '{field}' with non-string type: {type(value)}")
        
        # Handle shared_state (always store as string)
        if 'shared_state' in kwargs:
            shared_state = kwargs['shared_state']
            if isinstance(shared_state, dict):
                shared_state = json.dumps(shared_state)
            update_expr += ", agent_shared_state = :state"
            expr_values[':state'] = shared_state
        
        update_params = {
            'Key': {'job_id': job_id},
            'UpdateExpression': update_expr,
            'ExpressionAttributeValues': expr_values,
            'ReturnValues': 'ALL_NEW'
        }
        
        if expr_names:
            update_params['ExpressionAttributeNames'] = expr_names
        
        response = self.table.update_item(**update_params)
        return response['Attributes']
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID."""
        response = self.table.get_item(Key={'job_id': job_id})
        return response.get('Item')
    
    def get_latest_job_by_s3_uri(self, s3_uri: str) -> Optional[Dict[str, Any]]:
        """Get latest job for S3 URI."""
        response = self.table.query(
            IndexName='s3_uri-created_at-index',
            KeyConditionExpression='s3_uri = :s3_uri',
            ExpressionAttributeValues={':s3_uri': s3_uri},
            ScanIndexForward=False,
            Limit=1
        )
        items = response.get('Items', [])
        return items[0] if items else None
    
    def list_jobs_by_status(self, status: str = 'started', limit: int = 100, last_evaluated_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List jobs by status using GSI, sorted by created_at descending."""
        query_params = {
            'IndexName': 'status-created_at-index',
            'KeyConditionExpression': '#status = :status',
            'ExpressionAttributeNames': {'#status': 'status'},
            'ExpressionAttributeValues': {':status': status},
            'ScanIndexForward': False,  # Descending order (newest first)
            'Limit': limit
        }
        
        if last_evaluated_key:
            query_params['ExclusiveStartKey'] = last_evaluated_key
            
        response = self.table.query(**query_params)
        
        return {
            "jobs": response.get('Items', []),
            "count": len(response.get('Items', [])),
            "last_evaluated_key": response.get('LastEvaluatedKey'),
            "has_more": response.get('LastEvaluatedKey') is not None
        }
    
    def get_status_counts(self) -> Dict[str, int]:
        """Get count of jobs by status using GSI."""
        status_values = ['CREATED', 'PROCESSING', 'COMPLETED', 'FAILED']
        counts = {}
        
        for status in status_values:
            response = self.table.query(
                IndexName='status-created_at-index',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': status},
                Select='COUNT'
            )
            counts[status] = response.get('Count', 0)
            
        return counts
    
    def list_jobs_by_doc_type(self, doc_type: str, sender: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """List jobs by document type and optionally sender."""
        if sender:
            response = self.table.query(
                IndexName='doc_type-sender-index',
                KeyConditionExpression='doc_type = :doc_type AND sender = :sender',
                ExpressionAttributeValues={
                    ':doc_type': doc_type,
                    ':sender': sender
                },
                Limit=limit
            )
        else:
            response = self.table.query(
                IndexName='doc_type-sender-index',
                KeyConditionExpression='doc_type = :doc_type',
                ExpressionAttributeValues={':doc_type': doc_type},
                Limit=limit
            )
        return {
            "jobs": response.get('Items', []),
            "count": len(response.get('Items', []))
        }
    
    def list_recent_jobs(self, limit: int = 10, last_evaluated_key: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        List recent jobs across all statuses, sorted by created_at (most recent first).
        Uses scan operation since we need jobs across all statuses.
        
        Args:
            limit: Maximum number of jobs to return (1-100)
            last_evaluated_key: Pagination token for next page
            
        Returns:
            Dictionary containing jobs, pagination info, and metadata
        """
        # Validate limit
        limit = max(1, min(limit, 100))
        
        scan_params = {
            'ProjectionExpression': 'job_id, s3_uri, sender_name, #status, created_at, updated_at, doc_type',
            'ExpressionAttributeNames': {
                '#status': 'status'  # status is a reserved keyword
            },
            'Limit': limit
        }
        
        if last_evaluated_key:
            scan_params['ExclusiveStartKey'] = last_evaluated_key
        
        response = self.table.scan(**scan_params)
        
        jobs = response.get('Items', [])
        
        # Sort by created_at descending (most recent first)
        # Note: For production with large datasets, consider using a GSI with a constant partition key
        jobs.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        
        return {
            "jobs": jobs,
            "count": len(jobs),
            "last_evaluated_key": response.get('LastEvaluatedKey'),
            "scanned_count": response.get('ScannedCount', 0),
            "has_more": response.get('LastEvaluatedKey') is not None
        }
