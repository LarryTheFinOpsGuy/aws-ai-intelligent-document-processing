# AWS Lambda containers run with Lambda execution role permissions, not container user permissions
# checkov:skip=CKV_DOCKER_2:HEALTHCHECK not applicable for Lambda managed containers
# checkov:skip=CKV_DOCKER_3:Non-root user enforced by Lambda runtime
FROM public.ecr.aws/lambda/python:3.11-x86_64

# Copy lambda code
COPY infrastructure/core/aurora_data_loader/ ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["lambda_function.lambda_handler"] 
