import boto3
import os
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig

# Initialize AWS clients 
ssm_client = boto3.client('ssm')

def get_ssm_parameter(parameter_name):
    """Get parameter value from SSM Parameter Store"""
    response = ssm_client.get_parameter(Name=parameter_name)
    return response['Parameter']['Value']


# Get configuration from SSM
CREATE_JOB_LAMBDA_ARN = get_ssm_parameter('/agenticidp/agents/create_job_lambda_arn')
JOBS_TABLE_NAME = get_ssm_parameter('/agenticidp/agents/processing_jobs_table_name')

# Model configurations
MODELS = {
    'claude_4_5_sonnet': 'global.anthropic.claude-sonnet-4-5-20250929-v1:0',
    'claude_4_sonnet': 'global.anthropic.claude-sonnet-4-20250514-v1:0',
    'claude_4_5_haiku': 'global.anthropic.claude-haiku-4-5-20251001-v1:0',
    'nova_pro': 'us.amazon.nova-pro-v1:0',
    'nova_lite': 'global.amazon.nova-2-lite-v1:0',
}

# Default model
DEFAULT_MODEL = 'claude_4_5_haiku'

# Boto3 retry configuration for throttling
RETRY_CONFIG = BotocoreConfig(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)

def get_model(model_name=None, **kwargs):
    """
    Get a BedrockModel instance with retry configuration.
    
    Args:
        model_name: Simple model name from MODELS dict, or None for default
        **kwargs: Additional BedrockModel configuration (temperature, max_tokens, etc.)
    
    Returns:
        BedrockModel instance with retry handling
    """
    if model_name is None:
        model_name = DEFAULT_MODEL
    
    model_id = MODELS.get(model_name, MODELS[DEFAULT_MODEL])
    
    # Set default max_tokens if not provided
    if 'max_tokens' not in kwargs:
        kwargs['max_tokens'] = 40000
    
    # Enable reasoning for nova_lite with low effort
    if model_name == 'nova_lite':
        kwargs['additional_request_fields'] = {
            'reasoningConfig': {
                'type': 'enabled',
                'maxReasoningEffort': 'low'
            }
        }
    
    return BedrockModel(
        model_id=model_id,
        boto_client_config=RETRY_CONFIG,
        **kwargs
    )

