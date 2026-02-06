#!/usr/bin/env python3
"""
CDK Stack for Bedrock AgentCore Gateway and Gateway Targets using L1 constructs.
Includes Lambda container functions.
"""
import json
import os
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_bedrockagentcore as agentcore,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_ecr_assets as ecr_assets,
    CustomResource,
    Duration,
    CfnOutput
)
from constructs import Construct
from cdk_nag import NagSuppressions
from infrastructure.components.lambda_containers import LambdaContainersConstruct
from infrastructure.utils.asset_config import get_docker_asset_props


class GatewayStack(Stack):
    """Stack for Bedrock AgentCore Gateway and Gateway Targets using L1 constructs."""

    def __init__(self, scope: Construct, construct_id: str, config: dict, 
                 core_stack=None, aurora_stack=None, **kwargs) -> None:
        super().__init__(scope, construct_id, stack_name=f"AgenticIDP-{construct_id}", **kwargs)
        
        self.app_name = config.get("app_name", "agenticidp")
        self.env_name = config.get("environment", "dev")
        self.core_stack = core_stack
        self.aurora_stack = aurora_stack
        
        # Deploy Lambda container functions first
        self.lambda_containers = LambdaContainersConstruct(
            self, "LambdaContainers",
            config=config,
            core_stack=core_stack,
            aurora_stack=aurora_stack
        )
        
        # Load tool schemas
        self.schemas = self._load_schemas()
        
        # Create gateway IAM role
        self.gateway_role = self._create_gateway_role()
        
        # Create gateway using L1 construct
        self.gateway = self._create_gateway()
        
        # Create OAuth2 credential provider custom resource
        self.oauth2_provider = self._create_oauth2_credential_provider()
        
        # Create gateway targets using L1 constructs
        self.gateway_targets = self._create_gateway_targets()
        
        # Create SSM parameters
        self._create_parameters()
        
        # Create outputs for both Lambda functions and Gateway
        self._create_outputs()

    def _load_schemas(self) -> dict:
        """Load tool schemas from JSON files."""
        schemas = {}
        schema_dir = os.path.join(os.path.dirname(__file__), '..', 'schemas')
        
        schema_files = {
            's3_vector': 's3_vector_schema.json',
            's3_bucket': 's3_bucket_schema.json',
            'textractor': 'textractor_schema.json',
            'dynamodb_jobs': 'dynamodb_jobs_schema.json',
            'po_validator': 'po_validator_schema.json'
        }
        
        for tool_name, filename in schema_files.items():
            schema_path = os.path.join(schema_dir, filename)
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schemas[tool_name] = json.load(f)
            except FileNotFoundError:
                print(f"Warning: Schema file not found: {schema_path}")
                schemas[tool_name] = []
        
        return schemas

    def _create_gateway_role(self) -> iam.Role:
        """Create IAM role for gateway."""
        role = iam.Role(
            self, "GatewayRole",
            role_name=f"{self.app_name}-gateway-role",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=f"Gateway role for {self.app_name}"
        )
        
        # Lambda invoke permissions for all tool functions
        role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["lambda:InvokeFunction"],
            resources=[
                self.lambda_containers.s3_vector_function.function_arn,
                self.lambda_containers.s3_bucket_function.function_arn,
                self.lambda_containers.textractor_function.function_arn,
                self.lambda_containers.dynamodb_jobs_function.function_arn,
                self.lambda_containers.po_validator_function.function_arn
            ]
        ))
        
        return role

    def _create_gateway(self) -> agentcore.CfnGateway:
        """Create gateway using L1 construct."""
        
        # Gateway configuration
        authorizer_config = None
        if self.core_stack:
            authorizer_config = agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{self.core_stack.cognito.user_pool.user_pool_id}/.well-known/openid-configuration",
                    allowed_clients=[self.core_stack.cognito.gateway_app_client.user_pool_client_id]
                )
            )
        
        protocol_config = agentcore.CfnGateway.GatewayProtocolConfigurationProperty(
            mcp=agentcore.CfnGateway.MCPGatewayConfigurationProperty(
                search_type="SEMANTIC",
                supported_versions=["2025-03-26"]
            )
        )
        
        gateway = agentcore.CfnGateway(
            self, "Gateway",
            name=f"{self.app_name}-tool-gateway",
            authorizer_type="CUSTOM_JWT",
            protocol_type="MCP",
            role_arn=self.gateway_role.role_arn,
            description="Agenticidp operations with identity-based access",
            authorizer_configuration=authorizer_config,
            protocol_configuration=protocol_config
        )
        
        # Ensure policy is attached before gateway is created
        gateway.node.add_dependency(self.gateway_role)
        
        return gateway

    def _create_gateway_targets(self) -> dict:
        """Create all gateway targets using L1 constructs."""
        targets = {}
        
        # S3 Vector Target
        targets['s3_vector'] = self._create_gateway_target(
            "S3VectorTarget",
            f"{self.app_name}-s3-vector-target",
            "S3 Vector operations target",
            self.lambda_containers.s3_vector_function.function_arn,
            self.schemas['s3_vector']
        )
        
        # S3 Bucket Target
        targets['s3_bucket'] = self._create_gateway_target(
            "S3BucketTarget",
            f"{self.app_name}-s3-bucket-target",
            "S3 Bucket operations target",
            self.lambda_containers.s3_bucket_function.function_arn,
            self.schemas['s3_bucket']
        )
        
        # Textractor Target
        targets['textractor'] = self._create_gateway_target(
            "TextractorTarget",
            f"{self.app_name}-textractor-target",
            "Textractor operations target",
            self.lambda_containers.textractor_function.function_arn,
            self.schemas['textractor']
        )
        
        # DynamoDB Jobs Target
        targets['dynamodb_jobs'] = self._create_gateway_target(
            "DynamoDBJobsTarget",
            f"{self.app_name}-dynamodb-jobs-target",
            "DynamoDB Jobs operations target",
            self.lambda_containers.dynamodb_jobs_function.function_arn,
            self.schemas['dynamodb_jobs']
        )
        
        # PO Validator Target
        targets['po_validator'] = self._create_gateway_target(
            "POValidatorTarget",
            f"{self.app_name}-po-validator-target",
            "Purchase Order validation target",
            self.lambda_containers.po_validator_function.function_arn,
            self.schemas['po_validator']
        )
        
        return targets

    def _create_gateway_target(self, construct_id: str, target_name: str, 
                              description: str, lambda_arn: str, schema: list) -> agentcore.CfnGatewayTarget:
        """Create a gateway target using L1 construct."""
        
        target_config = agentcore.CfnGatewayTarget.TargetConfigurationProperty(
            mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                lambda_=agentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                    lambda_arn=lambda_arn,
                    tool_schema=agentcore.CfnGatewayTarget.ToolSchemaProperty(
                        inline_payload=schema  # Use schema directly as list
                    )
                )
            )
        )
        
        credential_config = [
            agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                credential_provider_type="GATEWAY_IAM_ROLE"
            )
        ]
        
        return agentcore.CfnGatewayTarget(
            self, construct_id,
            name=target_name,
            description=description,
            gateway_identifier=self.gateway.attr_gateway_identifier,
            target_configuration=target_config,
            credential_provider_configurations=credential_config
        )

    def _create_parameters(self):
        """Create SSM parameters."""
        
        # Gateway URL parameter
        ssm.StringParameter(
            self, "GatewayUrlParameter",
            parameter_name=f"/{self.app_name.lower()}/{self.env_name}/gateway-url",
            string_value=self.gateway.attr_gateway_url,
            description=f"Gateway URL for {self.app_name} {self.env_name} environment"
        )
        
        # Provider name parameter
        ssm.StringParameter(
            self, "ProviderNameParameter",
            parameter_name=f"/{self.app_name.lower()}/{self.env_name}/provider-name",
            string_value=f"{self.app_name}-{self.env_name}-oauth2-provider",
            description=f"OAuth2 credential provider name for {self.app_name} {self.env_name} environment"
        )
        
        # Provider scopes parameter
        ssm.StringParameter(
            self, "ProviderScopesParameter",
            parameter_name=f"/{self.app_name.lower()}/{self.env_name}/provider-scopes",
            string_value=f"{self.app_name}-gateway/invoke",
            description=f"Provider scopes for {self.app_name} {self.env_name} environment"
        )

    def _create_oauth2_credential_provider_lambda(self) -> lambda_.Function:
        """Create Lambda function for OAuth2 credential provider custom resource."""
        
        # Create Lambda execution role
        lambda_role = iam.Role(
            self, "OAuth2ProviderLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # CDK Nag suppression for AWS managed policy
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWSLambdaBasicExecutionRole is AWS recommended standard for Lambda CloudWatch Logs access. Wildcard required for dynamic log group creation.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                }
            ]
        )

        # Add Bedrock AgentCore permissions - scoped to account level
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:CreateOauth2CredentialProvider",
                "bedrock-agentcore:DeleteOauth2CredentialProvider",
                "bedrock-agentcore:GetOauth2CredentialProvider",
                "bedrock-agentcore:CreateTokenVault"
            ],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"]
        ))
        
        # Add Cognito permissions to get client secret - scoped to specific user pool
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cognito-idp:DescribeUserPoolClient"],
            resources=[self.core_stack.cognito.user_pool.user_pool_arn]
        ))
        
        # Add Secrets Manager permissions for OAuth2 credential provider
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:CreateSecret",
                "secretsmanager:DeleteSecret"
            ],
            resources=["*"]  # Required for OAuth2 credential provider creation
        ))

        # CDK Nag suppressions for IAM5 wildcards - applied to role after all policies are added
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Bedrock AgentCore requires wildcard for dynamic resource access.",
                    "appliesTo": ["Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Secrets Manager requires wildcard for OAuth2 credential provider creation - secret name is generated by Bedrock AgentCore service.",
                    "appliesTo": ["Resource::*"]
                }
            ],
            apply_to_children=True
        )
        
        # Build Docker image for OAuth2 provider Lambda
        oauth2_image = ecr_assets.DockerImageAsset(
            self, "OAuth2ProviderImage",
            **get_docker_asset_props(
                directory=".",
                dockerfile="infrastructure/lambda/oauth2_provider/Dockerfile",
                platform=ecr_assets.Platform.LINUX_AMD64
            )
        )
        
        return lambda_.DockerImageFunction(
            self, "OAuth2ProviderLambda",
            code=lambda_.DockerImageCode.from_ecr(
                repository=oauth2_image.repository,
                tag_or_digest=oauth2_image.image_tag
            ),
            role=lambda_role,
            timeout=Duration.minutes(5)
        )

    def _create_oauth2_credential_provider(self) -> CustomResource:
        """Create OAuth2 credential provider using custom resource."""
        
        # Create Lambda function for custom resource
        provider_lambda = self._create_oauth2_credential_provider_lambda()
        
        # Get Cognito configuration
        user_pool_id = self.core_stack.cognito.user_pool.user_pool_id if self.core_stack else ""
        client_id = self.core_stack.cognito.gateway_app_client.user_pool_client_id if self.core_stack else ""
        
        # Create custom resource
        return CustomResource(
            self, "OAuth2CredentialProvider",
            service_token=provider_lambda.function_arn,
            properties={
                "ProviderName": f"{self.app_name}-{self.env_name}-oauth2-provider",
                "DiscoveryUrl": f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration",
                "UserPoolId": user_pool_id,
                "ClientId": client_id,
                "Region": self.region,
                "AccountId": self.account
            }
        )

    def _create_outputs(self):
        """Create stack outputs."""
        
        # Gateway outputs
        CfnOutput(
            self, "GatewayRoleArn",
            value=self.gateway_role.role_arn,
            description="IAM role ARN for gateway"
        )
        
        CfnOutput(
            self, "GatewayId",
            value=self.gateway.attr_gateway_identifier,
            description="Gateway ID"
        )
        
        CfnOutput(
            self, "GatewayUrl",
            value=self.gateway.attr_gateway_url,
            description="Gateway URL"
        )
        
        # Lambda function outputs
        CfnOutput(
            self, "S3VectorFunctionArn",
            value=self.lambda_containers.s3_vector_function.function_arn,
            description="S3 Vector Tool Lambda function ARN"
        )
        
        CfnOutput(
            self, "S3VectorFunctionName",
            value=self.lambda_containers.s3_vector_function.function_name,
            description="S3 Vector Tool Lambda function name"
        )
        
        CfnOutput(
            self, "TextractorFunctionArn", 
            value=self.lambda_containers.textractor_function.function_arn,
            description="Textractor Tool Lambda function ARN"
        )
        
        CfnOutput(
            self, "TextractorFunctionName",
            value=self.lambda_containers.textractor_function.function_name,
            description="Textractor Tool Lambda function name"
        )
        
        CfnOutput(
            self, "S3BucketFunctionArn",
            value=self.lambda_containers.s3_bucket_function.function_arn,
            description="S3 Bucket Tool Lambda function ARN"
        )
        
        CfnOutput(
            self, "S3BucketFunctionName",
            value=self.lambda_containers.s3_bucket_function.function_name,
            description="S3 Bucket Tool Lambda function name"
        )
        
        CfnOutput(
            self, "DynamoDBJobsFunctionArn",
            value=self.lambda_containers.dynamodb_jobs_function.function_arn,
            description="DynamoDB Jobs Tool Lambda function ARN"
        )
        
        CfnOutput(
            self, "DynamoDBJobsFunctionName",
            value=self.lambda_containers.dynamodb_jobs_function.function_name,
            description="DynamoDB Jobs Tool Lambda function name"
        )
        
        CfnOutput(
            self, "POValidatorFunctionArn",
            value=self.lambda_containers.po_validator_function.function_arn,
            description="PO Validator Tool Lambda function ARN"
        )
        
        CfnOutput(
            self, "POValidatorFunctionName",
            value=self.lambda_containers.po_validator_function.function_name,
            description="PO Validator Tool Lambda function name"
        )
