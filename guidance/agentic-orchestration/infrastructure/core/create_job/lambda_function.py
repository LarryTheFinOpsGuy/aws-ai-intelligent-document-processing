#!/usr/bin/env python3
"""Lambda to invoke orchestrator and create job record."""
import json
import os
import boto3
from datetime import datetime

# AWS_REGION is automatically set by Lambda runtime
bedrock_client = boto3.client('bedrock-agentcore', region_name=os.environ['AWS_REGION'])
ssm_client = boto3.client('ssm', region_name=os.environ['AWS_REGION'])
dynamodb = boto3.resource('dynamodb', region_name=os.environ['AWS_REGION'])

PROCESSING_JOBS_TABLE = os.environ.get('PROCESSING_JOBS_TABLE', 'processing-jobs')

def get_orchestrator_arn():
    """Get orchestrator ARN from SSM Parameter Store."""
    try:
        response = ssm_client.get_parameter(Name='/agenticidp/agents/orchestrator_arn')
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting orchestrator ARN from SSM: {e}")
        return os.environ.get('ORCHESTRATOR_ARN', 'PLACEHOLDER_ARN')

def generate_timestamp():
    """Generate ISO timestamp."""
    return datetime.utcnow().isoformat() + 'Z'

def generate_job_id():
    """Generate unique job ID."""
    import uuid
    return str(uuid.uuid4())

def create_job(job_id, s3_uri):
    """Create job record in DynamoDB ProcessingJobs table."""
    table = dynamodb.Table(PROCESSING_JOBS_TABLE)
    timestamp = generate_timestamp()
    
    item = {
        'job_id': job_id,
        's3_uri': s3_uri,
        'created_at': timestamp,
        'updated_at': timestamp,
        'status': 'CREATED'
    }
    
    table.put_item(Item=item)
    return item

def invoke_orchestrator(session_id, s3_uri):
    """Invoke orchestrator agent and return response."""
    orchestrator_arn = get_orchestrator_arn()
    print(f"Using orchestrator ARN: {orchestrator_arn}")
    
    payload = {
        'action': 'orchestrate_graph',
        's3_uri': s3_uri
    }
    
    response = bedrock_client.invoke_agent_runtime(
        agentRuntimeArn=orchestrator_arn,
        runtimeSessionId=session_id,
        payload=json.dumps(payload).encode(),
        runtimeUserId="orchestrator_agent"
    )
    
    # Parse streaming response
    response_stream = response['response']
    result = {}
    
    for chunk in response_stream.iter_lines():
        if chunk:
            line = chunk.decode('utf-8')
            if line.startswith('data: '):
                data_str = line[6:]
                try:
                    result = json.loads(data_str)
                except json.JSONDecodeError:
                    pass
    
    return result

def lambda_handler(event, context):
    """Handle S3 event (direct or via EventBridge) and trigger orchestrator."""
    try:
        print(f"📦 Received event: {json.dumps(event)}")
        
        # Handle direct API invocation with s3_uri in body
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            if 's3_uri' in body:
                s3_uri = body['s3_uri']
                print(f"🔍 Processing direct API call with S3 URI: {s3_uri}")
                result = process_s3_file(s3_uri)
                return {
                    'statusCode': result['statusCode'],
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Session-Id',
                        'Access-Control-Allow-Methods': 'POST,OPTIONS'
                    },
                    'body': result['body']
                }
        
        # Handle EventBridge event format
        if 'detail' in event and event.get('source') == 'aws.s3':
            bucket = event['detail']['bucket']['name']
            key = event['detail']['object']['key']
            s3_uri = f"s3://{bucket}/{key}"
            
            print(f"🔍 Processing EventBridge S3 event: {s3_uri}")
            return process_s3_file(s3_uri)

        
        print(f"❌ Unrecognized event format")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Unrecognized event format'})
        }
        
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def process_s3_file(s3_uri):
    """Process a single S3 file."""
    # Generate job ID (will be used as session_id)
    job_id = generate_job_id()
    print(f"🆔 Generated job ID: {job_id}")
    
    # Create job record first
    print(f"💾 Creating job record...")
    job_record = create_job(job_id, s3_uri)
    print(f"✅ Created job record: {json.dumps(job_record, default=str)}")
    
    # Invoke orchestrator
    print(f"🚀 Invoking orchestrator...")
    orchestrator_response = invoke_orchestrator(job_id, s3_uri)
    print(f"📊 Orchestrator response: {json.dumps(orchestrator_response)}")
    
    # Extract values from orchestrator response
    session_id = orchestrator_response.get('session_id', job_id)
    document_uri = orchestrator_response.get('document_uri', s3_uri)
    message = orchestrator_response.get('message', 'Processing initiated')
    
    print(f"📋 Extracted values - session_id: {session_id}")
    
    # Return orchestrator response to caller
    response_body = {
        'session_id': session_id,
        'document_uri': document_uri,
        'message': message,
        'job_record': job_record
    }
    
    print(f"🎉 Returning success response")
    return {
        'statusCode': 200,
        'body': json.dumps(response_body, default=str)
    }
