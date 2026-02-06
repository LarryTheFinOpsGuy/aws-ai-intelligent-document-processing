# checkov:skip=CKV_DOCKER_2:HEALTHCHECK not applicable for Lambda/AgentCore managed containers
# checkov:skip=CKV_DOCKER_3:Non-root user enforced by Lambda runtime
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app

# All environment variables in one layer
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 

# Install build dependencies for compiling Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy shared utilities from parent context
COPY common/ common/

# Copy agent code
COPY agents/orchestratorgraph/ .

# Install from requirements file
RUN uv pip install --no-cache-dir -r requirements.txt

RUN uv pip install --no-cache-dir aws-opentelemetry-distro>=0.10.1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

# Use the full module path
CMD ["opentelemetry-instrument", "python", "-m", "orchestratorgraph_agent"]
