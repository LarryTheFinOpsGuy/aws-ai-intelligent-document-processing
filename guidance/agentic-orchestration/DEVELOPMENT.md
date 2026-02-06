# AgenticIDP - Development Guide

This guide covers local development, testing, and debugging workflows for AgenticIDP.

## Prerequisites for Local Development

- **Podman or Docker** for running observability tools
- **AWS CLI** configured with appropriate permissions
- **Python 3.11+** with uv package manager
- **DynamoDB tables** deployed (via Core stack)
- **Node.js 18+** for UI development

## Local Development Setup

### 1. Start Observability Tools

Start Jaeger for OpenTelemetry tracing:

```bash
# Using Podman
podman run -d --name jaeger \
  -p 16686:16686 \
  -p 14268:14268 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# Or using Docker
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 14268:14268 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

Access Jaeger UI at: http://localhost:16686

To restart Jaeger:
```bash
./restart-jaeger.sh
```

### 2. Run Local Orchestrator Agent

```bash
cd agents/orchestratorgraph
uv run orchestratorgraph_agent.py
```

Agent will be available at: http://localhost:8080

**Capture logs to file:**
```bash
cd agents/orchestratorgraph && uv run orchestratorgraph_agent.py > logs/output.log 2>&1
```

### 3. Use Local Testing Wrapper

```bash
uv run local_wrapper.py
```

## Local Testing Options

The `local_wrapper.py` provides several testing modes:

1. **Orchestrate**: Create job and process S3 document
2. **Get Status**: Check processing status
3. **Chat**: Interactive conversation with agent
4. **Assume Session**: Switch to existing session ID

## UI Development

### Run UI Locally

```bash
cd ui/orchestrator
npm run dev
```

UI will be available at: http://localhost:5173

### Build UI

```bash
cd ui/orchestrator
npm run build
```

### Deploy UI Only

```bash
cd ui/orchestrator
npm run deploy:cdk:dev
```

## Testing Deployed Agent

Use the deployed tester:

```bash
uv run orchestrator_deployed_tester.py
```

Or test via the web UI from the CloudFormation outputs.

## Sample Files Management

### Upload Sample Files

Upload sample documents to S3 for testing:

```bash
chmod +x infrastructure/upload-samples.sh
./infrastructure/upload-samples.sh
```

This creates a bucket named `agenticidp-samples-{accountid}` and uploads all files from the `sample-files` directory.

### Delete Sample Files

Empty and delete the sample files bucket:

```bash
chmod +x infrastructure/delete-samples-bucket.sh
./infrastructure/delete-samples-bucket.sh
```

## Utility Scripts

### Create Admin User

Manually create a Cognito admin user:

```bash
python scripts/create_admin_user.py
```

### Update UI Configuration

Update UI configuration from CloudFormation outputs:

```bash
python scripts/update-ui-config.py
```

### Test API Endpoints

Test deployed API endpoints:

```bash
python scripts/test-api-endpoints.py
```

### Scan Remaining Resources

Check for resources that weren't cleaned up:

```bash
python scripts/scan_remaining_resources.py
```

### Cleanup Remaining Resources

Remove resources that weren't deleted by CDK destroy:

```bash
python scripts/cleanup_remaining_resources.py
```

## Observability

### Jaeger Traces
- View distributed traces at http://localhost:16686
- Filter by service name: `orchestrator-agent`
- Inspect request flows and timing

### Agent Logs
- Console output from local agents
- Structured logging with context
- Error traces and stack traces

### Job Status
- Query via DynamoDB console
- Use local wrapper to check status
- View in deployed UI

## Infrastructure Development

### Generate CDK Nag Report

Run security checks on CDK infrastructure:

```bash
cd infrastructure
./generate-nag-report.sh
```

Report will be saved to `infrastructure/cdk-nag-report.txt`

### Reset Infrastructure

Reset infrastructure to clean state (WARNING: destructive):

```bash
cd infrastructure
python reset.py
```

## MCP Server (Optional)

The Model Context Protocol server provides additional tools for agent development.

### Run MCP Server

```bash
cd mcp
python po_validator_mcp.py
```

### Test MCP Server

```bash
cd mcp
python test_mcp.py
```

## Troubleshooting

### Agent Not Starting
- Check AWS credentials are configured
- Verify DynamoDB tables exist
- Check Python dependencies are installed

### UI Build Failures
- Run `npm install` in `ui/orchestrator`
- Check Node.js version (18+)
- Clear `node_modules` and reinstall

### Jaeger Not Accessible
- Verify container is running: `podman ps` or `docker ps`
- Check port 16686 is not in use
- Restart container: `./restart-jaeger.sh`

### Sample Files Not Uploading
- Verify `sample-files/` directory exists
- Check AWS credentials have S3 permissions
- Ensure bucket name matches account ID

## Development Workflow

1. **Start observability**: Launch Jaeger
2. **Deploy infrastructure**: `python deploy.py --skip-ui`
3. **Run local agent**: Test changes locally
4. **Upload samples**: Add test documents
5. **Test locally**: Use local wrapper
6. **Deploy changes**: `cdk deploy --all`
7. **Test deployed**: Use deployed tester or UI
8. **View traces**: Check Jaeger for issues

## Additional Resources

- **Agent Code**: `agents/orchestratorgraph/`
- **Gateway Tools**: `gateway/tools/`
- **Infrastructure**: `infrastructure/stacks/`
- **UI Source**: `ui/orchestrator/src/`
- **Test Scripts**: `scripts/`
