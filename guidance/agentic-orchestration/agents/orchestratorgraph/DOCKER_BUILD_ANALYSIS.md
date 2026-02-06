# Orchestrator Agent Docker Build Analysis

## Required Runtime Files (Included in Docker)

### Agent Files (9 files, ~81KB)
- `orchestratorgraph_agent.py` - Main agent entry point
- `analyzer_agent.py` - Document type classification
- `instructions_agent.py` - Instructions creation (uses prompts + schema)
- `extractor_agent.py` - Data extraction
- `matcher_agent.py` - Document matching
- `troubleshooter_agent.py` - Error handling (uses prompts + schema)
- `instructions_fixer_agent.py` - Instructions repair (uses prompts + schema)
- `save_instructions_agent.py` - Instructions persistence
- `validator_agent.py` - Validation logic

### Utils (7 files, ~22KB)
- `agentcore_gateway_client.py` - MCP client for gateway tools
- `config.py` - SSM parameter loading, model configuration
- `dynamodb_tracker.py` - Job tracking
- `invoke_agent_utils.py` - Agent invocation utilities
- `job_update_hook.py` - Strands hooks for job updates
- `processing_actions.py` - DynamoDB action logging
- `retry.py` - Retry logic for agent calls

### Data Files
- `prompts/po_meta_system_prompt.txt` (3.5KB) - System prompt for instructions/troubleshooter agents
- `doc_schema/purchase_order_schema.json` (5KB) - PO validation schema
- `requirements.txt` (94B) - Python dependencies

### Build Files
- `Dockerfile` (1.1KB)
- `.dockerignore` (updated)

**Total Runtime Size: ~112KB of Python code + dependencies**

## Excluded Files (Not Needed in Docker)

### Development/Debug Files
- `logs/` - Runtime logs from local development
- `scripts/` - Utility scripts for log analysis:
  - `download_session_logs.py`
  - `download_trace_logs.py`
  - `download_job_history.py`
  - `extract_session_summary.py`
  - `extract_log_summary.py`
  - `extract_update_job_calls.py`
  - `process_sessions.py`

### Local Configuration
- `.agentcore.json` - Local AgentCore configuration
- `run_agent.sh` - Local development script

### System Files
- `__pycache__/` - Python bytecode cache
- `.DS_Store` - macOS metadata

## Dependencies (from requirements.txt)

```
strands-agents
bedrock-agentcore-runtime
aws-opentelemetry-distro
```

Plus common utilities from `/common/` (shared across agents).

## Docker Build Optimization

The updated `.dockerignore` now explicitly excludes:
- Development logs and scripts (~9 Python files not needed)
- Local configuration files
- Shell scripts
- System metadata

This reduces the build context and final image size by excluding unnecessary development artifacts.
