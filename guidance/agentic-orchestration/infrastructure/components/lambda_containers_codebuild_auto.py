from constructs import Construct
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_codebuild as codebuild,
    aws_ecr as ecr,
    custom_resources as cr,
    Duration
)
import os

class LambdaContainersCodeBuildAutoConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, config: dict, core_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        app_name = config.get("app_name", "agenticidp")
        
        # Create ECR repositories
        self.s3_vector_repo = ecr.Repository(self, "S3VectorRepo", repository_name=f"{app_name}-s3-vector-tool")
        self.textractor_repo = ecr.Repository(self, "TextractorRepo", repository_name=f"{app_name}-textractor-tool")
        self.s3_bucket_repo = ecr.Repository(self, "S3BucketRepo", repository_name=f"{app_name}-s3-bucket-tool")
        
        # Create CodeBuild role
        codebuild_role = iam.Role(
            self, "CodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeBuildDeveloperAccess")
            ],
            inline_policies={
                "ECRPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["ecr:*"],
                            resources=[
                                self.s3_vector_repo.repository_arn,
                                self.textractor_repo.repository_arn,
                                self.s3_bucket_repo.repository_arn
                            ]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["ecr:GetAuthorizationToken"],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Create CodeBuild projects
        s3_vector_project = self._create_codebuild_project("S3VectorBuild", self.s3_vector_repo, "tools/s3_vector_tool", codebuild_role)
        textractor_project = self._create_codebuild_project("TextractorBuild", self.textractor_repo, "tools/textractor_tool", codebuild_role)
        s3_bucket_project = self._create_codebuild_project("S3BucketBuild", self.s3_bucket_repo, "tools/s3_bucket_tool", codebuild_role)
        
        # Create custom resource to trigger builds
        trigger_role = iam.Role(
            self, "TriggerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "CodeBuildPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                            resources=[
                                s3_vector_project.project_arn,
                                textractor_project.project_arn,
                                s3_bucket_project.project_arn
                            ]
                        )
                    ]
                )
            }
        )
        
        # Custom resource to trigger builds
        cr.AwsCustomResource(
            self, "TriggerBuilds",
            on_create=cr.AwsSdkCall(
                service="CodeBuild",
                action="startBuild",
                parameters={
                    "projectName": s3_vector_project.project_name
                },
                physical_resource_id=cr.PhysicalResourceId.of("s3-vector-build-trigger")
            ),
            role=trigger_role
        )
        
        cr.AwsCustomResource(
            self, "TriggerTextractorBuild",
            on_create=cr.AwsSdkCall(
                service="CodeBuild",
                action="startBuild",
                parameters={
                    "projectName": textractor_project.project_name
                },
                physical_resource_id=cr.PhysicalResourceId.of("textractor-build-trigger")
            ),
            role=trigger_role
        )
        
        cr.AwsCustomResource(
            self, "TriggerS3BucketBuild",
            on_create=cr.AwsSdkCall(
                service="CodeBuild",
                action="startBuild",
                parameters={
                    "projectName": s3_bucket_project.project_name
                },
                physical_resource_id=cr.PhysicalResourceId.of("s3-bucket-build-trigger")
            ),
            role=trigger_role
        )
        
        # Create Lambda role
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
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["s3vectors:*"],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["textract:AnalyzeDocument", "textract:StartDocumentAnalysis", "textract:GetDocumentAnalysis"],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Create Lambda functions using ECR images (will use latest tag after builds complete)
        self.s3_vector_function = lambda_.Function(
            self, "S3VectorFunction",
            function_name=f"{app_name}-s3-vector-tool",
            code=lambda_.EcrImageCode(repository=self.s3_vector_repo, tag="latest"),
            handler=lambda_.Handler.FROM_IMAGE,
            runtime=lambda_.Runtime.FROM_IMAGE,
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment={
                "REGION": config["region"],
                "VECTOR_BUCKET_NAME": core_stack.s3_buckets.vector_bucket_name,
                "INDEX_NAME": "documentsimilarity"
            },
            architecture=lambda_.Architecture.X86_64
        )
        
        self.textractor_function = lambda_.Function(
            self, "TextractorFunction",
            function_name=f"{app_name}-textractor-tool",
            code=lambda_.EcrImageCode(repository=self.textractor_repo, tag="latest"),
            handler=lambda_.Handler.FROM_IMAGE,
            runtime=lambda_.Runtime.FROM_IMAGE,
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            memory_size=2048,
            environment={
                "REGION": config["region"]
            },
            architecture=lambda_.Architecture.X86_64
        )
        
        self.s3_bucket_function = lambda_.Function(
            self, "S3BucketFunction",
            function_name=f"{app_name}-s3-bucket-tool",
            code=lambda_.EcrImageCode(repository=self.s3_bucket_repo, tag="latest"),
            handler=lambda_.Handler.FROM_IMAGE,
            runtime=lambda_.Runtime.FROM_IMAGE,
            role=self.lambda_role,
            timeout=Duration.minutes(15),
            memory_size=512,
            environment={
                "REGION": config["region"],
                "DOCUMENT_BUCKET": core_stack.s3_buckets.document_bucket.bucket_name
            },
            architecture=lambda_.Architecture.X86_64
        )
    
    def _create_codebuild_project(self, project_name: str, repo: ecr.Repository, dockerfile_path: str, role: iam.Role):
        return codebuild.Project(
            self, project_name,
            role=role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "pre_build": {
                        "commands": [
                            "echo Logging in to Amazon ECR...",
                            "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"
                        ]
                    },
                    "build": {
                        "commands": [
                            f"echo Build started on `date`",
                            f"echo Building the Docker image...",
                            f"docker build -t {repo.repository_name} {dockerfile_path}",
                            f"docker tag {repo.repository_name}:latest {repo.repository_uri}:latest"
                        ]
                    },
                    "post_build": {
                        "commands": [
                            "echo Build completed on `date`",
                            "echo Pushing the Docker image...",
                            f"docker push {repo.repository_uri}:latest"
                        ]
                    }
                }
            })
        )
