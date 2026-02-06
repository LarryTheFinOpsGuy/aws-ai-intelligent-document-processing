#!/usr/bin/env python3
"""Lambda to generate presigned POST URL for S3 uploads."""
import json
import os
import boto3
from datetime import datetime

s3_client = boto3.client('s3')

BUCKET_NAME = os.environ.get('DOCUMENT_BUCKET')
UPLOAD_PREFIX = 'uploads/'

def lambda_handler(event, context):
    """Generate presigned POST URL for file upload."""
    try:
        print(f"📦 Received event: {json.dumps(event)}")
        
        # Parse request body
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        file_name = body.get('fileName')
        content_type = body.get('contentType', 'application/pdf')
        
        if not file_name:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                'body': json.dumps({'error': 'fileName is required'})
            }
        
        # Generate unique key
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        key = f"{UPLOAD_PREFIX}{timestamp}-{file_name}"
        
        # Generate presigned POST
        presigned_post = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=key,
            Fields={'Content-Type': content_type},
            Conditions=[
                {'Content-Type': content_type},
                ['content-length-range', 1, 104857600]  # 1 byte to 100MB
            ],
            ExpiresIn=3600
        )
        
        print(f"✅ Generated presigned POST for: {key}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'presignedPost': presigned_post,
                'key': key,
                's3Uri': f"s3://{BUCKET_NAME}/{key}"
            })
        }
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({'error': str(e)})
        }
