# AWS Lambda containers run with Lambda execution role permissions, not container user permissions
# checkov:skip=CKV_DOCKER_2:HEALTHCHECK not applicable for Lambda/AgentCore managed containers
# checkov:skip=CKV_DOCKER_3:Non-root user enforced by Lambda runtime
FROM public.ecr.aws/lambda/python:3.11

# Copy shared utilities from parent context
COPY common/ ${LAMBDA_TASK_ROOT}/common/

# Copy lambda code
COPY infrastructure/core/create_job/ ${LAMBDA_TASK_ROOT}/

RUN pip install --no-cache-dir boto3

# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["lambda_function.lambda_handler"] 
