#!/usr/bin/env python3
"""
CDK Stack for Bedrock AgentCore Orchestrator Graph Agent and Automation.
Combines orchestrator agent runtime and S3 event automation.
"""
import json
import os
from aws_cdk import (
    Stack,
    Duration,
    aws_iam as iam,
    aws_ecr as ecr,
    aws_ecr_assets as ecr_assets,
    aws_bedrock as bedrock,
    aws_bedrockagentcore as agentcore,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_events as events,
    aws_events_targets as targets,
    aws_ssm as ssm,
    RemovalPolicy,
    CfnOutput
)
from cdk_nag import NagSuppressions
from constructs import Construct
from infrastructure.utils.asset_config import get_docker_asset_props


class AgentStack(Stack):
    """Stack for Orchestrator Graph Agent and Automation using Bedrock AgentCore Runtime."""

    def __init__(self, scope: Construct, construct_id: str, config: dict, core_stack=None, **kwargs) -> None:
        super().__init__(scope, construct_id, stack_name=f"AgenticIDP-{construct_id}", **kwargs)
        
        self.app_name = config.get("app_name", "agenticidp")
        self.core_stack = core_stack
        
        # Create orchestrator agent first
        self.orchestrator_repository = self._create_orchestrator_repository()
        self.orchestrator_image = self._create_orchestrator_image()
        self.orchestrator_runtime_role = self._create_orchestrator_runtime_role()
        self.orchestrator_runtime = self._create_orchestrator_runtime()
        
        # Create guardrail for contextual grounding
        self.guardrail = self._create_contextual_grounding_guardrail()
        
        # Create automation components
        self._create_automation_lambda()
        self._create_s3_event_trigger()
        
        # Create SSM parameters
        self._create_ssm_parameters()
        
        # Create outputs
        self._create_outputs()

    def _create_orchestrator_repository(self) -> ecr.Repository:
        """Create ECR repository for orchestrator agent."""
        return ecr.Repository(
            self, "OrchestratorRepository",
            repository_name=f"bedrock-agentcore-{self.app_name}_orchestratorgraph",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
        )

    def _create_orchestrator_image(self) -> ecr_assets.DockerImageAsset:
        """Build and push Docker image for orchestrator agent."""
        
        return ecr_assets.DockerImageAsset(
            self, "OrchestratorImage",
            **get_docker_asset_props(
                directory=".",
                dockerfile="agents/orchestratorgraph/Dockerfile"
            )
        )

    def _create_orchestrator_runtime_role(self) -> iam.Role:
        """Create IAM role for orchestrator agent runtime with comprehensive permissions."""
        
        # Create trust policy with conditions
        assumable_principal = iam.PrincipalWithConditions(
            principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": self.account
                }
            }
        )
        
        role = iam.Role(
            self, "OrchestratorRuntimeRole",
            assumed_by=assumable_principal,
            role_name=f"{self.app_name}-orchestrator-runtime-role",
            description="IAM role for Bedrock AgentCore Orchestrator Runtime"
        )
        
        # ECR Image Access
        role.add_to_policy(iam.PolicyStatement(
            sid="ECRImageAccess",
            effect=iam.Effect.ALLOW,
            actions=[
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer"
            ],
            resources=[f"arn:aws:ecr:{self.region}:{self.account}:repository/*"]
        ))
        
        # ECR token access (requires wildcard)
        role.add_to_policy(iam.PolicyStatement(
            sid="ECRTokenAccess",
            effect=iam.Effect.ALLOW,
            actions=["ecr:GetAuthorizationToken"],
            resources=["*"]
        ))
        
        # CloudWatch Logs - Create log groups
        role.add_to_policy(iam.PolicyStatement(
            sid="CloudWatchLogsCreate",
            effect=iam.Effect.ALLOW,
            actions=["logs:CreateLogGroup"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"]
        ))
        
        # CloudWatch Logs - Describe (broader scope needed)
        role.add_to_policy(iam.PolicyStatement(
            sid="CloudWatchLogsDescribe",
            effect=iam.Effect.ALLOW,
            actions=["logs:DescribeLogGroups"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:*"]
        ))
        
        # CloudWatch Logs - Stream operations
        role.add_to_policy(iam.PolicyStatement(
            sid="CloudWatchLogsStream",
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
        ))
        
        # X-Ray tracing (requires wildcard)
        role.add_to_policy(iam.PolicyStatement(
            sid="XRayTracing",
            effect=iam.Effect.ALLOW,
            actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
            resources=["*"]
        ))
        
        # CloudWatch Metrics (requires wildcard)
        role.add_to_policy(iam.PolicyStatement(
            sid="CloudWatchMetrics",
            effect=iam.Effect.ALLOW,
            actions=["cloudwatch:PutMetricData"],
            resources=["*"]
        ))
        
        # Bedrock AgentCore Runtime - Operations
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockAgentCoreRuntime",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:InvokeAgentRuntime",
                "bedrock-agentcore:InvokeAgentRuntimeForUser"
            ],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/*"]
        ))
        
        # Bedrock AgentCore Memory - Create (requires wildcard for creation)
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockAgentCoreMemoryCreate",
            effect=iam.Effect.ALLOW,
            actions=["bedrock-agentcore:CreateMemory"],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"]
        ))
        
        # Bedrock AgentCore Memory - Operations
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockAgentCoreMemory",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:CreateEvent",
                "bedrock-agentcore:GetEvent",
                "bedrock-agentcore:GetMemory",
                "bedrock-agentcore:GetMemoryRecord",
                "bedrock-agentcore:ListActors",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:ListMemoryRecords",
                "bedrock-agentcore:ListSessions",
                "bedrock-agentcore:DeleteEvent",
                "bedrock-agentcore:DeleteMemoryRecord",
                "bedrock-agentcore:RetrieveMemoryRecords"
            ],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/*"]
        ))
        
        # Bedrock AgentCore Token Vault - API Key Credential Provider
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockAgentCoreTokenVaultAPIKey",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:CreateApiKeyCredentialProvider",
                "bedrock-agentcore:DeleteApiKeyCredentialProvider",
                "bedrock-agentcore:GetApiKeyCredentialProvider",
                "bedrock-agentcore:ListApiKeyCredentialProviders"
            ],
            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default/apikeycredentialprovider/*"]
        ))
        
        # Bedrock AgentCore Workload Identity
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockAgentCoreWorkloadIdentity",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:CreateWorkloadIdentity",
                "bedrock-agentcore:DeleteWorkloadIdentity",
                "bedrock-agentcore:GetWorkloadIdentity",
                "bedrock-agentcore:ListWorkloadIdentities",
                "bedrock-agentcore:GetResourceOauth2Token"
            ],
            resources=[
                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default/*",
                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:workload-identity-directory/default"
                ]
        ))
        
        # Bedrock AgentCore Token Vault - OAuth2 Credential Provider
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockAgentCoreTokenVaultOAuth2",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:CreateOauth2CredentialProvider",
                "bedrock-agentcore:DeleteOauth2CredentialProvider",
                "bedrock-agentcore:GetOauth2CredentialProvider",
                "bedrock-agentcore:ListOauth2CredentialProviders",
                "bedrock-agentcore:GetResourceOauth2Token"
            ],
            resources=[
                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default/*",
                f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:token-vault/default"
                ]
        ))
        
        # Bedrock foundation models
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockModelInvocation",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
                ],
            resources=[
                f"arn:aws:bedrock:*::foundation-model/*",
                f"arn:aws:bedrock:{self.region}:{self.account}:*"
                ]
        ))
        
        # Bedrock guardrails
        role.add_to_policy(iam.PolicyStatement(
            sid="BedrockGuardrails",
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:ApplyGuardrail"
            ],
            resources=[
                f"arn:aws:bedrock:{self.region}:{self.account}:guardrail/*"
            ]
        ))
        
        # Secrets Manager - scoped to account level
        role.add_to_policy(iam.PolicyStatement(
            sid="SecretsManagerService",
            effect=iam.Effect.ALLOW,
            actions=["secretsmanager:GetSecretValue"],
            resources=[f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:*"]
        ))
        
        # SSM Parameter Store - Scoped to AgenticIDP parameters
        role.add_to_policy(iam.PolicyStatement(
            sid="SSMParameterStore",
            effect=iam.Effect.ALLOW,
            actions=[
                "ssm:GetParametersByPath",
                "ssm:GetParameter"
            ],
            resources=[
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.app_name.lower()}/dev",
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.app_name.lower()}/agents/*"
            ]
        ))
        
        # DynamoDB access for state tracking - scoped to specific table
        role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:UpdateItem",
                "dynamodb:GetItem",
                "dynamodb:PutItem"
            ],
            resources=[
                self.core_stack.processing_jobs_table.table_arn,
                self.core_stack.processing_actions_table.table_arn
            ]
        ))
        
        # Lambda invocation for create job - scoped to specific function
        role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["lambda:InvokeFunction"],
            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:{self.app_name}-create-job"]
        ))
        
        # CDK Nag suppressions for IAM5 wildcards - applied to role and its policies
        NagSuppressions.add_resource_suppressions(
            role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "ECR, CloudWatch, Bedrock AgentCore, Bedrock models, Secrets Manager, and SSM require wildcards per AWS service design and agent runtime requirements.",
                    "appliesTo": [
                        "Resource::*",
                        "Resource::arn:aws:ecr:<AWS::Region>:<AWS::AccountId>:repository/*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/bedrock-agentcore/runtimes/*",
                        "Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
                        "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:*",
                        "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:memory/*",
                        "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:runtime/*",
                        "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:token-vault/default/*",
                        "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:token-vault/default/apikeycredentialprovider/*",
                        "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:workload-identity-directory/default/*",
                        "Resource::arn:aws:bedrock:*::foundation-model/*",
                        "Resource::arn:aws:bedrock:<AWS::Region>:<AWS::AccountId>:*",
                        "Resource::arn:aws:bedrock:<AWS::Region>:<AWS::AccountId>:guardrail/*",
                        "Resource::arn:aws:secretsmanager:<AWS::Region>:<AWS::AccountId>:secret:*",
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/agenticidp/agents/*"
                    ]
                }
            ],
            apply_to_children=True
        )
        
        return role

    def _create_contextual_grounding_guardrail(self) -> bedrock.CfnGuardrail:
        """Create a Bedrock guardrail with contextual grounding check."""
        
        guardrail = bedrock.CfnGuardrail(
            self, "ContextualGroundingGuardrail",
            name=f"{self.app_name}-contextual-grounding",
            description="Guardrail for contextual grounding validation in document extraction",
            blocked_input_messaging="Input contains content that cannot be grounded in the provided context.",
            blocked_outputs_messaging="Output contains content that cannot be grounded in the provided context.",
            contextual_grounding_policy_config=bedrock.CfnGuardrail.ContextualGroundingPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContextualGroundingFilterConfigProperty(
                        type="GROUNDING",
                        threshold=0.75  # Threshold for grounding confidence (0.0-1.0)
                    ),
                    bedrock.CfnGuardrail.ContextualGroundingFilterConfigProperty(
                        type="RELEVANCE", 
                        threshold=0.75  # Threshold for relevance confidence (0.0-1.0)
                    )
                ]
            )
        )
        
        return guardrail

    def _create_orchestrator_runtime(self) -> agentcore.CfnRuntime:
        """Create Bedrock AgentCore Runtime using L1 construct."""
        
        runtime = agentcore.CfnRuntime(
            self, "OrchestratorRuntime",
            agent_runtime_name="agenticidp_orchestratorgraph",
            role_arn=self.orchestrator_runtime_role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=self.orchestrator_image.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            environment_variables={
                "AWS_REGION": self.region
            }
        )
        
        # Ensure role and all policies are fully created before runtime
        runtime.add_dependency(self.orchestrator_runtime_role.node.default_child)
        
        # Add dependencies for inline policies
        for child in self.orchestrator_runtime_role.node.children:
            if child.node.id.startswith("DefaultPolicy"):
                runtime.add_dependency(child.node.default_child)
        
        return runtime

    def _create_automation_lambda(self):
        """Create automation Lambda function for S3 event processing."""
        
        # Get document bucket and processing tables from core stack
        document_bucket = self.core_stack.s3_buckets.document_bucket
        processing_jobs_table = self.core_stack.processing_jobs_table
        processing_actions_table = self.core_stack.processing_actions_table
        
        # No Docker image needed for zip deployment
        
        # Create IAM role for Lambda
        lambda_role = iam.Role(
            self, "CreateJobLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "CustomLambdaExecution": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=[
                                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/{self.app_name}-create-job:*"
                            ]
                        )
                    ]
                )
            }
        )
        
        # CDK Nag suppression for CloudWatch Logs wildcard
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [{"id": "AwsSolutions-IAM5", "reason": "CloudWatch Logs requires wildcard for log stream creation.", "appliesTo": ["Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/agenticidp-create-job:*"]}]
        )
        
        # Grant DynamoDB permissions
        processing_jobs_table.grant_write_data(lambda_role)
        processing_actions_table.grant_write_data(lambda_role)
        
        # Grant Bedrock AgentCore permissions - scoped to specific orchestrator runtime
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:InvokeAgentRuntime","bedrock-agentcore:InvokeAgentRuntimeForUser"],
                resources=[
                    self.orchestrator_runtime.attr_agent_runtime_arn,
                    f"{self.orchestrator_runtime.attr_agent_runtime_arn}/runtime-endpoint/*"
                ]
            )
        )
                # SSM Parameter Store - Scoped to AgenticIDP parameters
        lambda_role.add_to_policy(iam.PolicyStatement(
            sid="SSMParameterStore",
            effect=iam.Effect.ALLOW,
            actions=[
                "ssm:GetParametersByPath",
                "ssm:GetParameter"
            ],
            resources=[
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.app_name.lower()}/dev",
                f"arn:aws:ssm:{self.region}:{self.account}:parameter/{self.app_name.lower()}/agents/*"
            ]
        ))
        
        # Grant S3 read permissions
        document_bucket.grant_read(lambda_role)

        # CDK Nag suppressions for IAM5 wildcards - applied to role after all policies added
        NagSuppressions.add_resource_suppressions(
            lambda_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3, DynamoDB GSI, Bedrock AgentCore runtime, and SSM require wildcards per AWS service design.",
                    "appliesTo": [
                        "Action::s3:GetBucket*",
                        "Action::s3:GetObject*",
                        "Action::s3:List*",
                        "Resource::<S3BucketsDocumentBucket6A8C8FBB.Arn>/*",
                        "Resource::<ProcessingActionsTableCBCEB9EA.Arn>/index/*",
                        "Resource::<ProcessingJobsTable00D8CF66.Arn>/index/*",
                        "Resource::<OrchestratorRuntime.AgentRuntimeArn>/runtime-endpoint/*",
                        "Resource::arn:aws:ssm:<AWS::Region>:<AWS::AccountId>:parameter/agenticidp/agents/*"
                    ]
                }
            ],
            apply_to_children=True
        )
        
        # Create Lambda function
        self.create_job_function = lambda_.Function(
            self, "CreateJobFunction",
            function_name=f"{self.app_name}-create-job",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/infrastructure/core/create_job/* /asset-output/ && "
                        "cp -r /asset-input/common /asset-output/"
                    ]
                }
            ),
            role=lambda_role,
            timeout=Duration.minutes(5),
            environment={
                "PROCESSING_JOBS_TABLE": processing_jobs_table.table_name,
                "ORCHESTRATOR_ARN": self.orchestrator_runtime.attr_agent_runtime_arn
            }
        )
        
        # CDK Nag suppression - already using latest available runtime
        NagSuppressions.add_resource_suppressions(
            self.create_job_function,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."
                }
            ]
        )

    def _create_s3_event_trigger(self):
        """Create S3 event trigger for automation using EventBridge."""
        
        # Create EventBridge rule for S3 events
        rule = events.Rule(
            self, "S3ProcessingRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {
                        "name": [self.core_stack.s3_buckets.document_bucket.bucket_name]
                    },
                    "object": {
                        "key": [{"prefix": "for_processing/"}]
                    }
                }
            )
        )
        
        # Add Lambda as target
        rule.add_target(targets.LambdaFunction(self.create_job_function))
        
        # Enable EventBridge notifications on bucket
        self.core_stack.s3_buckets.document_bucket.enable_event_bridge_notification()

    def _create_ssm_parameters(self):
        """Create SSM parameters for agent configuration."""
        
        # Store orchestrator agent ARN in SSM Parameter Store
        ssm.StringParameter(
            self, "OrchestratorAgentArnParameter", 
            parameter_name=f"/{self.app_name.lower()}/agents/orchestrator_arn",
            string_value=self.orchestrator_runtime.attr_agent_runtime_arn,
            description=f"Orchestrator agent ARN for {self.app_name}"
        )
        
        # Store Lambda function ARN in SSM Parameter Store
        ssm.StringParameter(
            self, "CreateJobLambdaArnParameter",
            parameter_name=f"/{self.app_name.lower()}/agents/create_job_lambda_arn",
            string_value=self.create_job_function.function_arn,
            description=f"Create job Lambda function ARN for {self.app_name}"
        )
        
        # Store guardrail ID in SSM Parameter Store
        ssm.StringParameter(
            self, "GuardrailIdParameter",
            parameter_name=f"/{self.app_name.lower()}/guardrails/contextual_grounding_id",
            string_value=self.guardrail.attr_guardrail_id,
            description=f"Contextual grounding guardrail ID for {self.app_name}"
        )

    def _create_outputs(self):
        """Create stack outputs."""
        
        # Orchestrator outputs
        CfnOutput(
            self, "OrchestratorRuntimeArn",
            value=self.orchestrator_runtime.attr_agent_runtime_arn,
            description="Orchestrator Agent Runtime ARN"
        )
        
        CfnOutput(
            self, "OrchestratorRuntimeName",
            value=self.orchestrator_runtime.agent_runtime_name,
            description="Orchestrator Agent Runtime Name"
        )
        
        CfnOutput(
            self, "OrchestratorRoleArn",
            value=self.orchestrator_runtime_role.role_arn,
            description="Orchestrator Agent Runtime Role ARN"
        )
        
        # Guardrail outputs
        CfnOutput(
            self, "GuardrailId",
            value=self.guardrail.attr_guardrail_id,
            description="Contextual Grounding Guardrail ID"
        )
        
        CfnOutput(
            self, "GuardrailArn",
            value=self.guardrail.attr_guardrail_arn,
            description="Contextual Grounding Guardrail ARN"
        )
        
        # Automation outputs
        CfnOutput(
            self, "CreateJobFunctionArn",
            value=self.create_job_function.function_arn,
            description="Create Job Lambda Function ARN"
        )
        
        CfnOutput(
            self, "CreateJobFunctionName",
            value=self.create_job_function.function_name,
            description="Create Job Lambda Function Name"
        )
