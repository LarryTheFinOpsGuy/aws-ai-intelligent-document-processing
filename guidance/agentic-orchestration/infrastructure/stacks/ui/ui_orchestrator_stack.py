#!/usr/bin/env python3
"""
CDK Stack for Modern Orchestrator UI API endpoints.
Provides REST API Gateway with Lambda functions for job listing, job actions, and chat functionality.
"""

from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_ssm as ssm,
    aws_logs as logs,
    RemovalPolicy
)
from cdk_nag import NagSuppressions
from constructs import Construct


class UIOrchestratorStack(Stack):
    """Stack for Modern Orchestrator UI API endpoints."""

    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        config: dict,
        core_stack=None,
        agent_stack=None,
        gateway_stack=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, stack_name=f"AgenticIDP-{construct_id}", **kwargs)
        
        self.app_name = config.get("app_name", "agenticidp")
        self.core_stack = core_stack
        self.agent_stack = agent_stack
        self.gateway_stack = gateway_stack
        
        # Create Lambda functions
        self.jobs_lambda = self._create_jobs_lambda()
        self.job_actions_lambda = self._create_job_actions_lambda()
        self.job_flow_lambda = self._create_job_flow_lambda()
        self.job_search_lambda = self._create_job_search_lambda()
        self.chat_lambda = self._create_chat_lambda()
        self.upload_lambda = self._create_upload_lambda()
        self.processing_rules_lambda = self._create_processing_rules_lambda()
        
        # Create API Gateway
        self.api = self._create_api_gateway()
        
        # CDK Nag suppressions for Lambda runtimes
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026.",
                    "appliesTo": ["Resource::*"]
                }
            ]
        )
        
        # CDK Nag suppression for AWS managed policies
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWSLambdaBasicExecutionRole is AWS recommended standard for Lambda CloudWatch Logs access. Wildcard required for dynamic log group creation.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                }
            ]
        )

        # CDK Nag suppressions for IAM5 wildcards
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK LogRetention construct requires account-wide access to manage log group retention policies.",
                    "appliesTo": ["Resource::*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "DynamoDB GSI queries require wildcard paths for index access patterns.",
                    "appliesTo": ["Resource::<ProcessingJobsTable.Arn>/index/*", "Resource::<ProcessingActionsTable.Arn>/index/*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Bedrock AgentCore agent invocation requires wildcard for dynamic agent resources.",
                    "appliesTo": ["Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 multipart upload requires Abort* wildcard action for upload cleanup.",
                    "appliesTo": ["Action::s3:Abort*"]
                }
            ]
        )
        
        # Create outputs
        self._create_outputs()

    def _create_jobs_lambda(self) -> lambda_.Function:
        """Create Lambda function for job listing API."""
        
        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self, "JobsLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant DynamoDB read permissions
        self.core_stack.processing_jobs_table.grant_read_data(lambda_role)
        
        # Add IAM5 suppressions
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [{"id": "AwsSolutions-IAM5", "reason": "DynamoDB GSI queries require wildcard paths for index access patterns.", "appliesTo": ["Resource::<ProcessingJobsTable00D8CF66.Arn>/index/*"]}],
            apply_to_children=True
        )
        
        # Create Lambda function
        jobs_function = lambda_.Function(
            self, "JobsFunction",
            function_name=f"{self.app_name}-ui-jobs",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_jobs/* /asset-output/ && "
                        "cp -r /asset-input/common /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "PROCESSING_JOBS_TABLE": self.core_stack.processing_jobs_table.table_name
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        
        NagSuppressions.add_resource_suppressions(
            jobs_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        return jobs_function

    def _create_job_actions_lambda(self) -> lambda_.Function:
        """Create Lambda function for job actions API."""
        
        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self, "JobActionsLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant DynamoDB read permissions
        self.core_stack.processing_jobs_table.grant_read_data(lambda_role)
        self.core_stack.processing_actions_table.grant_read_data(lambda_role)
        
        # Add IAM5 suppressions
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [{"id": "AwsSolutions-IAM5", "reason": "DynamoDB GSI queries require wildcard paths.", "appliesTo": ["Resource::<ProcessingActionsTableCBCEB9EA.Arn>/index/*", "Resource::<ProcessingJobsTable00D8CF66.Arn>/index/*"]}],
            apply_to_children=True
        )
        
        # Create Lambda function
        job_actions_function = lambda_.Function(
            self, "JobActionsFunction",
            function_name=f"{self.app_name}-ui-job-actions",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_job_actions/* /asset-output/ && "
                        "cp -r /asset-input/common /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "PROCESSING_JOBS_TABLE": self.core_stack.processing_jobs_table.table_name,
                "PROCESSING_ACTIONS_TABLE": self.core_stack.processing_actions_table.table_name
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        
        NagSuppressions.add_resource_suppressions(
            job_actions_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        return job_actions_function

    def _create_job_flow_lambda(self) -> lambda_.Function:
        """Create Lambda function for job flow visualization API."""
        
        lambda_role = iam.Role(
            self, "JobFlowLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        self.core_stack.processing_jobs_table.grant_read_data(lambda_role)
        self.core_stack.processing_actions_table.grant_read_data(lambda_role)
        
        # Add IAM5 suppressions
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [{"id": "AwsSolutions-IAM5", "reason": "DynamoDB GSI queries require wildcard paths.", "appliesTo": ["Resource::<ProcessingActionsTableCBCEB9EA.Arn>/index/*", "Resource::<ProcessingJobsTable00D8CF66.Arn>/index/*"]}],
            apply_to_children=True
        )
        
        job_flow_function = lambda_.Function(
            self, "JobFlowFunction",
            function_name=f"{self.app_name}-ui-job-flow",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_job_flow/* /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "PROCESSING_JOBS_TABLE": self.core_stack.processing_jobs_table.table_name,
                "PROCESSING_ACTIONS_TABLE": self.core_stack.processing_actions_table.table_name
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        NagSuppressions.add_resource_suppressions(
            job_flow_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        
        return job_flow_function

    def _create_job_search_lambda(self) -> lambda_.Function:
        """Create Lambda function for job search API."""
        
        lambda_role = iam.Role(
            self, "JobSearchLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        self.core_stack.processing_jobs_table.grant_read_data(lambda_role)
        
        # Add IAM5 suppressions
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [{"id": "AwsSolutions-IAM5", "reason": "DynamoDB GSI queries require wildcard paths for index access patterns.", "appliesTo": ["Resource::<ProcessingJobsTable00D8CF66.Arn>/index/*"]}],
            apply_to_children=True
        )
        
        job_search_function = lambda_.Function(
            self, "JobSearchFunction",
            function_name=f"{self.app_name}-ui-job-search",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_job_search/* /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "PROCESSING_JOBS_TABLE": self.core_stack.processing_jobs_table.table_name
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        NagSuppressions.add_resource_suppressions(
            job_search_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        
        return job_search_function

    def _create_chat_lambda(self) -> lambda_.Function:
        """Create Lambda function for chat API."""
        
        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self, "ChatLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant Bedrock AgentCore permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser"
                ],
                resources=[
                    self.agent_stack.orchestrator_runtime.attr_agent_runtime_arn,
                    f"{self.agent_stack.orchestrator_runtime.attr_agent_runtime_arn}/runtime-endpoint/*"
                ]
            )
        )
        
        # Grant SSM parameter access
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParametersByPath"
                ],
                resources=[
                    f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.app_name.lower()}/agents/*"
                ]
            )
        )
        
        # CDK Nag suppressions for wildcards
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [
                {"id": "AwsSolutions-IAM5", "reason": "SSM parameter access requires wildcard for agent configuration parameters.", "appliesTo": ["Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/agenticidp/agents/*"]},
                {"id": "AwsSolutions-IAM5", "reason": "Bedrock AgentCore runtime endpoint requires wildcard for session management.", "appliesTo": ["Resource::<OrchestratorRuntime.AgentRuntimeArn>/runtime-endpoint/*"]}
            ],
            apply_to_children=True
        )
        
        # Create Lambda function
        chat_function = lambda_.Function(
            self, "ChatFunction",
            function_name=f"{self.app_name}-ui-chat",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_chat/* /asset-output/ && "
                        "cp -r /asset-input/common /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.minutes(5),
            environment={
                "ORCHESTRATOR_ARN": self.agent_stack.orchestrator_runtime.attr_agent_runtime_arn
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        NagSuppressions.add_resource_suppressions(
            chat_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        
        return chat_function

    def _create_upload_lambda(self) -> lambda_.Function:
        """Create Lambda function for presigned upload URL generation."""
        
        lambda_role = iam.Role(
            self, "UploadLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant S3 permissions
        self.core_stack.s3_buckets.document_bucket.grant_put(lambda_role)
        
        # Add IAM5 suppressions
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [{"id": "AwsSolutions-IAM5", "reason": "S3 document bucket requires object-level wildcard.", "appliesTo": ["Resource::<S3BucketsDocumentBucket6A8C8FBB.Arn>/*"]}],
            apply_to_children=True
        )
        
        upload_function = lambda_.Function(
            self, "UploadFunction",
            function_name=f"{self.app_name}-ui-upload",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_upload/* /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "DOCUMENT_BUCKET": self.core_stack.s3_buckets.document_bucket.bucket_name
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        NagSuppressions.add_resource_suppressions(
            upload_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        
        return upload_function

    def _create_processing_rules_lambda(self) -> lambda_.Function:
        """Create Lambda function for Processing Rules API."""
        
        lambda_role = iam.Role(
            self, "ProcessingRulesLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant permission to invoke S3 Vector Lambda and S3 Bucket Lambda
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=[
                self.gateway_stack.lambda_containers.s3_vector_function.function_arn,
                self.gateway_stack.lambda_containers.s3_bucket_function.function_arn
            ]
        ))
        
        processing_rules_function = lambda_.Function(
            self, "ProcessingRulesFunction",
            function_name=f"{self.app_name}-ui-processing-rules",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/lambda/ui_processing_rules/* /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.seconds(30),
            environment={
                "S3_VECTOR_LAMBDA_NAME": self.gateway_stack.lambda_containers.s3_vector_function.function_name,
                "S3_BUCKET_LAMBDA_NAME": self.gateway_stack.lambda_containers.s3_bucket_function.function_name
            },
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        NagSuppressions.add_resource_suppressions(
            processing_rules_function,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        
        
        return processing_rules_function

    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create API Gateway with Cognito authorizer."""
        
        # Get Cognito User Pool from Core Stack
        user_pool = cognito.UserPool.from_user_pool_id(
            self, "UserPool",
            self.core_stack.cognito.user_pool.user_pool_id
        )
        
        # Create Cognito authorizer
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
            authorizer_name="orchestrator-ui-authorizer"
        )
        
        # Create CloudWatch log group for API Gateway access logs
        api_log_group = logs.LogGroup(
            self, "APIGatewayAccessLogs",
            log_group_name=f"/aws/apigateway/{self.app_name}-orchestrator-ui-api",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Create IAM role for API Gateway CloudWatch logging (account-level requirement)
        api_gateway_cloudwatch_role = iam.Role(
            self, "ApiGatewayCloudWatchRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonAPIGatewayPushToCloudWatchLogs")
            ]
        )
        
        # CDK Nag suppression for AWS managed policy
        NagSuppressions.add_resource_suppressions(
            api_gateway_cloudwatch_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AmazonAPIGatewayPushToCloudWatchLogs is AWS required managed policy for API Gateway logging.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"]
                }
            ]
        )
        
        # Set the CloudWatch role for API Gateway account settings
        apigateway.CfnAccount(
            self, "ApiGatewayAccount",
            cloud_watch_role_arn=api_gateway_cloudwatch_role.role_arn
        )
        
        # Create API Gateway
        api = apigateway.RestApi(
            self, "OrchestratorAPI",
            rest_api_name=f"{self.app_name}-orchestrator-ui-api",
            description="API for Modern Orchestrator UI",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                access_log_destination=apigateway.LogGroupLogDestination(api_log_group),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True
                )
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["http://localhost:3000", "http://localhost:3001", "https://*"],
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date", 
                    "Authorization",
                    "X-Api-Key",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent",
                    "Access-Control-Allow-Origin",
                    "Access-Control-Allow-Headers",
                    "Access-Control-Allow-Methods"
                ],
                allow_credentials=False,
                max_age=Duration.seconds(86400)  # 24 hours
            ),
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.REGIONAL]
            )
        )
        
        # Create /api resource
        api_resource = api.root.add_resource("api")
        
        # Create /api/jobs endpoint
        jobs_resource = api_resource.add_resource(
            "jobs",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date", 
                    "Authorization",
                    "X-Api-Key",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        jobs_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.jobs_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/jobs/search endpoint
        search_resource = jobs_resource.add_resource(
            "search",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date", 
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        search_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.job_search_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/jobs/{job_id}/actions endpoint
        job_id_resource = jobs_resource.add_resource("{job_id}")
        actions_resource = job_id_resource.add_resource(
            "actions",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        actions_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.job_actions_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/jobs/{job_id}/flow endpoint
        flow_resource = job_id_resource.add_resource(
            "flow",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        flow_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.job_flow_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/chat endpoint
        chat_resource = api_resource.add_resource(
            "chat",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        chat_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                self.chat_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/orchestrate endpoint (uses existing create-job Lambda)
        orchestrate_resource = api_resource.add_resource(
            "orchestrate",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        orchestrate_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                self.agent_stack.create_job_function,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/upload endpoint (presigned URL generation)
        upload_resource = api_resource.add_resource(
            "upload",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        upload_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                self.upload_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # Create /api/processing-rules endpoints
        processing_rules_resource = api_resource.add_resource(
            "processing-rules",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        
        # GET /api/processing-rules - List all
        processing_rules_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.processing_rules_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # POST /api/processing-rules/search - Search by sender
        search_rules_resource = processing_rules_resource.add_resource(
            "search",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        search_rules_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                self.processing_rules_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # GET/PATCH /api/processing-rules/{id}
        rule_id_resource = processing_rules_resource.add_resource(
            "{id}",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        rule_id_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.processing_rules_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        rule_id_resource.add_method(
            "PATCH",
            apigateway.LambdaIntegration(
                self.processing_rules_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # POST /api/processing-rules/s3-bucket - Instructions management
        s3_bucket_resource = processing_rules_resource.add_resource(
            "s3-bucket",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Session-Id",
                    "X-Request-Id",
                    "X-Amz-Date",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent"
                ],
                allow_credentials=False
            )
        )
        s3_bucket_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                self.processing_rules_lambda,
                proxy=True
            ),
            authorizer=cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # CDK Nag suppressions for demo/guidance application
        NagSuppressions.add_resource_suppressions(
            api,
            [
                {
                    "id": "AwsSolutions-APIG2",
                    "reason": "Demo/guidance application. Request validation not required for demo purposes with trusted inputs."
                },
                {
                    "id": "AwsSolutions-APIG3",
                    "reason": "Demo/guidance application. WAF integration adds cost and complexity not needed for demo purposes."
                }
            ],
            apply_to_children=True
        )
        
        return api

    def _create_outputs(self):
        """Create stack outputs."""
        
        CfnOutput(
            self, "APIGatewayURL",
            value=self.api.url,
            description="API Gateway URL for Orchestrator UI"
        )
        
        CfnOutput(
            self, "APIGatewayId",
            value=self.api.rest_api_id,
            description="API Gateway ID"
        )
        
        CfnOutput(
            self, "JobsLambdaArn",
            value=self.jobs_lambda.function_arn,
            description="Jobs Lambda Function ARN"
        )
        
        CfnOutput(
            self, "JobActionsLambdaArn",
            value=self.job_actions_lambda.function_arn,
            description="Job Actions Lambda Function ARN"
        )
        
        CfnOutput(
            self, "ChatLambdaArn",
            value=self.chat_lambda.function_arn,
            description="Chat Lambda Function ARN"
        )