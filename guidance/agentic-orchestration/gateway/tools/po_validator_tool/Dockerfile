# AWS Lambda containers run with Lambda execution role permissions, not container user permissions
# checkov:skip=CKV_DOCKER_2:HEALTHCHECK not applicable for Lambda/AgentCore managed containers
# checkov:skip=CKV_DOCKER_3:Non-root user enforced by Lambda runtime
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements and install dependencies
COPY gateway/tools/po_validator_tool/requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

# Copy function code
COPY gateway/tools/po_validator_tool/lambda_function.py ${LAMBDA_TASK_ROOT}
COPY gateway/tools/po_validator_tool/purchase_order_schema.json ${LAMBDA_TASK_ROOT}

 # nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["lambda_function.lambda_handler"] 
