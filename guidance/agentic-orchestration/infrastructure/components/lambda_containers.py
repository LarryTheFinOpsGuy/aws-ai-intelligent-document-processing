from constructs import Construct
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    Duration,
    Stack
)
from cdk_nag import NagSuppressions
import os

class LambdaContainersConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, config: dict, core_stack, aurora_stack=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        app_name = config.get("app_name", "agenticidp")
        self.region = Stack.of(self).region
        self.account = Stack.of(self).account
        
        # Create IAM role for Lambda functions
        self.lambda_role = iam.Role(
            self, "LambdaRole",
            role_name=f"{app_name}-lambda-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "LambdaPolicy": iam.PolicyDocument(
                    statements=[
                        # S3 permissions - scoped to specific buckets
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject"
                            ],
                            resources=[
                                f"{core_stack.s3_buckets.document_bucket.bucket_arn}/*"
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:ListBucket",
                            ],
                            resources=[
                                core_stack.s3_buckets.document_bucket.bucket_arn
                            ]
                        ),
                        # S3 Vectors permissions - scoped to specific vector bucket
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3vectors:*"
                            ],
                            resources=[
                                f"arn:aws:s3vectors:{self.region}:{self.account}:bucket/{core_stack.s3_buckets.vector_bucket_name}",
                                f"arn:aws:s3vectors:{self.region}:{self.account}:bucket/{core_stack.s3_buckets.vector_bucket_name}/*"
                            ]
                        ),
                        # Bedrock permissions - scoped to specific regions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*"
                            ]
                        ),
                        # Textract permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "textract:AnalyzeDocument",
                                "textract:StartDocumentAnalysis",
                                "textract:GetDocumentAnalysis"
                            ],
                            resources=["*"]
                        ),
                        # DynamoDB permissions - scoped to specific table
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:PutItem",
                                "dynamodb:GetItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:Query",
                                "dynamodb:Scan"
                            ],
                            resources=[
                                core_stack.processing_jobs_table.table_arn,
                                f"{core_stack.processing_jobs_table.table_arn}/index/*",
                                core_stack.processing_actions_table.table_arn,
                                f"{core_stack.processing_actions_table.table_arn}/index/*"
                            ]
                        ),
                        # Aurora DSQL permissions - read-only access
                        # Note: Using DbConnectAdmin for now as Lambda uses admin token
                        # TODO: Create custom read-only database role and use DbConnect
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dsql:GetCluster",
                                "dsql:DbConnectAdmin"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # CDK Nag suppression for AWS managed policy
        NagSuppressions.add_resource_suppressions(
            self.lambda_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWSLambdaBasicExecutionRole is AWS recommended standard for Lambda CloudWatch Logs access. Wildcard required for dynamic log group creation.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                }
            ]
        )
        
        # CDK Nag suppressions for IAM5 wildcards - applied to role and its policies
        NagSuppressions.add_resource_suppressions(
            self.lambda_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "DSQL connection requires wildcard resource per AWS service design.",
                    "appliesTo": ["Action::dsql:*", "Resource::*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 Vectors operations scoped to specific vector bucket.",
                    "appliesTo": ["Action::s3vectors:*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 Vectors bucket requires object-level wildcard for vector operations.",
                    "appliesTo": ["Resource::arn:aws:s3vectors:<AWS::Region>:<AWS::AccountId>:bucket/agenticidp-vectors-<AWS::AccountId>/*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Textract document analysis requires wildcard resource per AWS service design.",
                    "appliesTo": ["Action::textract:*", "Resource::*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Bedrock model access requires wildcard to support multiple foundation models.",
                    "appliesTo": ["Resource::arn:aws:bedrock:<AWS::Region>::foundation-model/*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 document bucket requires object-level wildcard for file operations.",
                    "appliesTo": ["Resource::<S3BucketsDocumentBucket6A8C8FBB.Arn>/*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "DynamoDB GSI queries require wildcard paths for index access patterns.",
                    "appliesTo": [
                        "Resource::<ProcessingActionsTableCBCEB9EA.Arn>/index/*",
                        "Resource::<ProcessingJobsTable00D8CF66.Arn>/index/*"
                    ]
                }
            ],
            apply_to_children=True
        )
        
        # Get paths to Lambda source directories
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gateway_tools_dir = os.path.join(current_dir, "../../../gateway/tools")
        
        # S3 Vector Tool Container Function
        self.s3_vector_function = lambda_.DockerImageFunction(
            self, "S3VectorFunction",
            function_name=f"{app_name}-s3-vector-tool",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=".",  # Root context
                file="gateway/tools/s3_vector_tool/Dockerfile.cdk"
            ),
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                "REGION": self.region,
                "VECTOR_BUCKET_NAME": core_stack.s3_buckets.vector_bucket_name,
                "INDEX_NAME": "documentsimilarity"
            },
            architecture=lambda_.Architecture.X86_64
        )
        
        # Textractor Tool Container Function
        self.textractor_function = lambda_.DockerImageFunction(
            self, "TextractorFunction",
            function_name=f"{app_name}-textractor-tool",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=".",  # Root context
                file="gateway/tools/textractor_tool/Dockerfile.cdk"
            ),
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            memory_size=2048,
            environment={
                "REGION": self.region
            },
            architecture=lambda_.Architecture.X86_64
        )
        
        # S3 Bucket Tool Function
        self.s3_bucket_function = lambda_.Function(
            self, "S3BucketFunction",
            function_name=f"{app_name}-s3-bucket-tool",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                "gateway",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/tools/s3_bucket_tool/* /asset-output/ && "
                        "cp -r /asset-input/utilities/* /asset-output/"
                    ]
                }
            ),
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            memory_size=512,
            environment={
                "REGION": self.region,
                "DOCUMENT_BUCKET": core_stack.s3_buckets.document_bucket.bucket_name
            },
            architecture=lambda_.Architecture.X86_64
        )
        
        # DynamoDB Jobs Tool Function
        self.dynamodb_jobs_function = lambda_.Function(
            self, "DynamoDBJobsFunction",
            function_name=f"{app_name}-dynamodb-jobs-tool",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                ".",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash", "-c",
                        "cp -r /asset-input/gateway/tools/dynamodb_jobs_tool/* /asset-output/ && "
                        "cp -r /asset-input/common /asset-output/"
                    ]
                }
            ),
            role=self.lambda_role,
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "REGION": self.region,
                "PROCESSING_JOBS_TABLE": core_stack.processing_jobs_table.table_name,
                "PROCESSING_ACTIONS_TABLE": core_stack.processing_actions_table.table_name
            },
            architecture=lambda_.Architecture.X86_64
        )
        
        # CDK Nag suppressions for Lambda runtimes
        for function in [self.s3_bucket_function, self.dynamodb_jobs_function]:
            NagSuppressions.add_resource_suppressions(
                function,
                [
                    {
                        "id": "AwsSolutions-L1",
                        "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."
                    }
                ]
            )
        
        # PO Validator Tool Container Function
        self.po_validator_function = lambda_.DockerImageFunction(
            self, "POValidatorFunction",
            function_name=f"{app_name}-po-validator-tool",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=".",  # Root context
                file="gateway/tools/po_validator_tool/Dockerfile"
            ),
            role=self.lambda_role,
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "REGION": self.region,
                "DOCUMENT_BUCKET_NAME": core_stack.s3_buckets.document_bucket.bucket_name,
                "CLUSTER_ID": aurora_stack.dsql_cluster.attr_identifier if aurora_stack else "demo-cluster"
            },
            architecture=lambda_.Architecture.X86_64
        )
