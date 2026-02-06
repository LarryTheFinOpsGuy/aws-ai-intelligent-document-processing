# UI Orchestrator Stack

This directory contains the CDK infrastructure for the Modern Orchestrator UI API endpoints.

## Stack Overview

The `UIOrchestratorStack` provides REST API endpoints for the React-based Modern Orchestrator UI to communicate with the backend services.

### Components

1. **API Gateway**: REST API with Cognito authorizer
2. **Lambda Functions**: Three endpoints for UI functionality
3. **IAM Roles**: Proper permissions for DynamoDB and AgentCore access

### API Endpoints

- `GET /api/jobs` - List recent processing jobs
- `GET /api/jobs/{job_id}/actions` - Get detailed job action history  
- `POST /api/chat` - Send messages to AgentCore orchestrator

### Dependencies

- **CoreStack**: Provides Cognito User Pool and DynamoDB tables
- **AgentStack**: Provides AgentCore orchestrator runtime

### Deployment

The stack is automatically included when deploying with `cdk deploy --all` and will be deployed after its dependencies.

### Environment Variables

The Lambda functions receive the following environment variables:
- `PROCESSING_JOBS_TABLE`: DynamoDB table name for jobs
- `PROCESSING_ACTIONS_TABLE`: DynamoDB table name for actions  
- `ORCHESTRATOR_ARN`: AgentCore runtime ARN for chat functionality

### Outputs

- `APIGatewayURL`: Base URL for the REST API
- `APIGatewayId`: API Gateway resource ID
- Lambda function ARNs for monitoring and debugging