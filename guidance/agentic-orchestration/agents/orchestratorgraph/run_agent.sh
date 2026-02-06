#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Set OTEL endpoint for local Jaeger
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"

# Run orchestrator agent with output piped to log file
echo "Starting orchestrator agent..."
echo "OTEL endpoint: $OTEL_EXPORTER_OTLP_ENDPOINT"
echo "Logs will be written to logs/output.log"
echo "Press Ctrl+C to stop"

uv run orchestratorgraph_agent.py > logs/output.log 2>&1
