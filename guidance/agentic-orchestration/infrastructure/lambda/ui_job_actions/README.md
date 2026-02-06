# UI Job Actions Lambda Function

## Overview

This Lambda function provides the API endpoint for retrieving detailed job action history for the Modern Orchestrator UI. It queries both the `processing-jobs` and `processing-actions` DynamoDB tables to return comprehensive job information.

## API Endpoint

**GET** `/api/jobs/{job_id}/actions`

### Path Parameters

- `job_id` (required): Unique identifier for the job

### Response Format

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_details": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "s3_uri": "s3://bucket/document.pdf",
    "sender_name": "Acme Corp",
    "status": "completed",
    "created_at": 1234567890000,
    "updated_at": 1234567890001,
    "doc_type": "invoice",
    "current_step": "extraction"
  },
  "actions": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "started_at": "2024-01-01T10:00:00Z",
      "agent": "analyzer",
      "action_type": "document_analysis",
      "status": "completed",
      "completed_at": "2024-01-01T10:05:00Z",
      "result": {"confidence": 0.95},
      "error_message": ""
    }
  ],
  "total_actions": 1
}
```

### Error Responses

#### 400 Bad Request
```json
{
  "error": "Validation Error",
  "message": "job_id is required in the path"
}
```

#### 404 Not Found
```json
{
  "error": "Job Not Found",
  "message": "Job with ID {job_id} does not exist"
}
```

#### 500 Internal Server Error
```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred"
}
```

## Implementation Details

### Data Sources

1. **processing-jobs table**: Provides job details including status, timestamps, and metadata
2. **processing-actions table**: Provides detailed action history with agent information

### Key Features

- **Comprehensive Error Handling**: Validates input, handles missing jobs, and provides detailed error messages
- **Structured Logging**: Uses Python logging module for debugging and monitoring
- **CORS Support**: Includes proper CORS headers for cross-origin requests
- **Consistent Response Format**: Follows the same pattern as other UI API endpoints
- **Action Sorting**: Returns actions sorted by `started_at` timestamp (chronological order)

### Dependencies

- `boto3`: AWS SDK for DynamoDB access
- `common.dynamodb_jobs`: Shared utility for job operations

### Environment Variables

- `PROCESSING_JOBS_TABLE`: Name of the DynamoDB jobs table
- `PROCESSING_ACTIONS_TABLE`: Name of the DynamoDB actions table
- `AWS_REGION`: AWS region (defaults to us-west-2)

## Testing

Unit tests are located in `tests/test_ui_job_actions_lambda.py` and cover:

- Input validation
- Response formatting
- Error handling scenarios
- DynamoDB integration (mocked)
- Edge cases (missing fields, empty results)

Run tests with:
```bash
python -m pytest tests/test_ui_job_actions_lambda.py -v
```

## Deployment

This Lambda function is deployed as part of the `UIOrchestratorStack` CDK stack. The deployment:

1. Bundles the Lambda code from `infrastructure/lambda/ui_job_actions/`
2. Includes the `common` module for shared utilities
3. Creates IAM role with DynamoDB read permissions
4. Configures API Gateway integration with Cognito authorization

Deploy with:
```bash
cdk deploy UIOrchestr-Dev
```

## Requirements Validation

This implementation satisfies the following requirements from the Modern Orchestrator UI specification:

- **Requirement 3.3**: Display detailed job history with all processing actions when user clicks on a job
- **Requirement 7.1**: Provide GET endpoints for job listing and detailed job actions from DynamoDB tables
- **Requirement 7.4**: Accept session IDs in request headers for context management (via CORS headers)
- **Requirement 7.5**: Provide structured JSON responses with appropriate HTTP status codes
