# UI Jobs API Lambda Function

This Lambda function provides the `/api/jobs` endpoint for the Modern Orchestrator UI, allowing retrieval of recent processing jobs with pagination and sorting.

## Endpoint

**GET** `/api/jobs`

## Authentication

Requires Cognito JWT token in the `Authorization` header.

## Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 10 | Number of jobs to return (1-100) |
| `last_key` | string | - | Pagination token for next page (JSON encoded) |

## Response Format

```json
{
  "jobs": [
    {
      "job_id": "string",
      "s3_uri": "string", 
      "sender_name": "string",
      "status": "string",
      "created_at": "number",
      "doc_type": "string"
    }
  ],
  "total_count": "number",
  "has_more": "boolean",
  "next_key": "string (optional)"
}
```

## Response Fields

- **jobs**: Array of job objects sorted by `created_at` (most recent first)
- **total_count**: Number of jobs returned in this response
- **has_more**: Boolean indicating if more jobs are available
- **next_key**: Pagination token for next page (only present if `has_more` is true)

## Job Object Fields

- **job_id**: Unique identifier for the job
- **s3_uri**: S3 URI of the processed document
- **sender_name**: Name of the document sender (defaults to "Unknown")
- **status**: Current job status (e.g., "started", "processing", "completed", "failed")
- **created_at**: Job creation timestamp (milliseconds since epoch)
- **doc_type**: Type of document (e.g., "invoice", "purchase_order")

## Error Responses

### 400 Bad Request
```json
{
  "error": "Validation Error",
  "message": "Invalid query parameters: <details>"
}
```

### 403 Forbidden
```json
{
  "error": "Access Denied", 
  "message": "Insufficient permissions to access jobs"
}
```

### 404 Not Found
```json
{
  "error": "Resource Not Found",
  "message": "Jobs table not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Database Error",
  "message": "Unable to retrieve jobs",
  "details": {
    "code": "DynamoDB error code"
  }
}
```

## Example Usage

### Basic Request
```bash
GET /api/jobs?limit=5
Authorization: Bearer <cognito-jwt-token>
```

### Response
```json
{
  "jobs": [
    {
      "job_id": "abc123-def456-ghi789",
      "s3_uri": "s3://documents/invoice-2024-001.pdf",
      "sender_name": "Acme Corp",
      "status": "completed",
      "created_at": 1703980800000,
      "doc_type": "invoice"
    }
  ],
  "total_count": 1,
  "has_more": false
}
```

### Pagination Request
```bash
GET /api/jobs?limit=10&last_key=%7B%22job_id%22%3A%22abc123%22%7D
Authorization: Bearer <cognito-jwt-token>
```

## Implementation Details

- Uses DynamoDB scan operation to retrieve jobs across all statuses
- Sorts results by `created_at` in descending order (most recent first)
- Implements efficient pagination using DynamoDB's `LastEvaluatedKey`
- Validates input parameters and enforces reasonable limits
- Provides comprehensive error handling and logging
- Uses shared `DynamoDBJobsClient` utility for database operations

## Performance Considerations

- Scan operations can be expensive for large datasets
- For production with many jobs, consider implementing a GSI with a constant partition key
- Current implementation sorts in memory - suitable for moderate datasets
- Pagination helps limit memory usage and response times

## Testing

Run the test suite:
```bash
python -m pytest tests/test_ui_jobs_lambda.py -v
```

## Dependencies

- `boto3`: AWS SDK for DynamoDB operations
- `common.dynamodb_jobs`: Shared DynamoDB utilities
- Environment variables:
  - `PROCESSING_JOBS_TABLE`: DynamoDB table name
  - `AWS_REGION`: AWS region (defaults to us-west-2)