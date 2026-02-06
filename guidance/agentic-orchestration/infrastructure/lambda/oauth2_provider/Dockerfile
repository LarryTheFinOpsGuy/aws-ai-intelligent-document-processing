# AWS Lambda containers run with Lambda execution role permissions, not container user permissions
# checkov:skip=CKV_DOCKER_2:HEALTHCHECK not applicable for Lambda/AgentCore managed containers
# checkov:skip=CKV_DOCKER_3:Non-root user enforced by Lambda runtime
FROM public.ecr.aws/lambda/python:3.11

# Copy shared utilities from parent context
COPY common/ ${LAMBDA_TASK_ROOT}/common/

# Copy lambda code
COPY infrastructure/lambda/oauth2_provider/ ${LAMBDA_TASK_ROOT}/

# Install latest boto3
RUN pip install --no-cache-dir --upgrade boto3 cfnresponse

# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["app.handler"] 

