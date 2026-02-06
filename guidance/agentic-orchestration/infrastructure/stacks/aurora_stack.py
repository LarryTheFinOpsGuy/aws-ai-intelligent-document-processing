from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    CustomResource,
    Duration,
    RemovalPolicy,
    aws_dsql as dsql,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_ecr_assets as ecr_assets
)
from cdk_nag import NagSuppressions
from infrastructure.utils.asset_config import get_docker_asset_props

class AuroraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, stack_name=f"AgenticIDP-{construct_id}", **kwargs)
        
        app_name = config.get("app_name", "agenticidp")
        account_id = Stack.of(self).account
        
        # Reference existing access logs bucket from Core stack
        access_logs_bucket = s3.Bucket.from_bucket_name(
            self, "AccessLogsBucket",
            f"{app_name}-access-logs-{account_id}"
        )
        
        # Create Aurora DSQL cluster
        self.dsql_cluster = dsql.CfnCluster(
            self, "DSQLCluster",
            deletion_protection_enabled=False,
            tags=[
                {"key": "Name", "value": "agentic-idp-sample"},
                {"key": "Environment", "value": config.get("environment", "dev")}
            ]
        )
        
        # S3 bucket for sample data
        data_bucket = s3.Bucket(
            self, "SampleDataBucket",
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
            enforce_ssl=True,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="sample-data/"
        )
        
        # Upload sample data to S3
        sample_data_deployment = s3deploy.BucketDeployment(
            self, "SampleDataDeployment",
            sources=[s3deploy.Source.asset("infrastructure/sample_data")],
            destination_bucket=data_bucket
        )
        
        # CDK Nag suppression for BucketDeployment
        NagSuppressions.add_resource_suppressions(
            sample_data_deployment,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK BucketDeployment requires S3 object wildcards.",
                    "appliesTo": ["Action::s3:GetObject*", "Action::s3:GetBucket*", "Action::s3:List*", "Resource::<SampleDataBucketD9EE4C71.Arn>/*"]
                }
            ],
            apply_to_children=True
        )
        
        # CDK Nag suppression for BucketDeployment singleton Lambda
        # The hash in the resource ID is content-based and will change if source files change
        # Find the actual custom resource path dynamically
        for node in self.node.find_all():
            if node.node.path.startswith(f"{self.node.path}/Custom::CDKBucketDeployment"):
                NagSuppressions.add_resource_suppressions_by_path(
                    self,
                    f"/{node.node.path}",
                    [
                        {
                            "id": "AwsSolutions-L1",
                            "reason": "BucketDeployment is a CDK-managed custom resource. Runtime version is controlled by CDK framework."
                        },
                        {
                            "id": "AwsSolutions-IAM4",
                            "reason": "BucketDeployment is a CDK-managed custom resource that uses AWSLambdaBasicExecutionRole.",
                            "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                        },
                        {
                            "id": "AwsSolutions-IAM5",
                            "reason": "BucketDeployment is a CDK-managed custom resource that uses wildcard S3 actions scoped to specific buckets.",
                            "appliesTo": [
                                "Action::s3:GetBucket*",
                                "Action::s3:GetObject*",
                                "Action::s3:List*",
                                "Action::s3:Abort*",
                                "Action::s3:DeleteObject*",
                                "Resource::arn:<AWS::Partition>:s3:::cdk-hnb659fds-assets-<AWS::AccountId>-<AWS::Region>/*",
                                "Resource::<SampleDataBucketD9EE4C71.Arn>/*"
                            ]
                        }
                    ],
                    apply_to_children=True
                )
                break
        
        # Build Docker image for data loader Lambda
        data_loader_image = ecr_assets.DockerImageAsset(
            self, "DataLoaderImage",
            **get_docker_asset_props(
                directory=".",
                dockerfile="infrastructure/core/aurora_data_loader/Dockerfile",
                platform=ecr_assets.Platform.LINUX_AMD64
            )
        )
        
        # IAM role for Lambda
        lambda_role = iam.Role(
            self, "DataLoaderRole",
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
        
        # Add permissions for DSQL and S3
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dsql:GetCluster",
                    "dsql:DbConnectAdmin"
                ],
                resources=["*"]
            )
        )
        
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetObject"],
                resources=[f"{data_bucket.bucket_arn}/*"]
            )
        )
        
        # CDK Nag suppressions for IAM5 wildcards - applied to role and its policies

        
        NagSuppressions.add_resource_suppressions(

        
            lambda_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda requires CloudWatch Logs wildcard for dynamic log stream creation.",
                    "appliesTo": ["Resource::*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 bucket requires object-level wildcard for sample data file access.",
                    "appliesTo": ["Resource::<SampleDataBucketD9EE4C71.Arn>/*"]
                }
            ],
            apply_to_children=True
        )
        
        # Lambda function for data loading custom resource
        data_loader_function = lambda_.DockerImageFunction(
            self, "DataLoaderFunction",
            function_name=f"{app_name}-aurora-data-loader",
            code=lambda_.DockerImageCode.from_ecr(
                repository=data_loader_image.repository,
                tag_or_digest=data_loader_image.image_tag
            ),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=512
        )
        
        # Custom resource to load data
        data_loader = CustomResource(
            self, "DataLoader",
            service_token=data_loader_function.function_arn,
            properties={
                "ClusterId": self.dsql_cluster.attr_identifier,
                "Region": self.region,
                "BucketName": data_bucket.bucket_name,
                "ClusterStatus": self.dsql_cluster.attr_status  # Force dependency on cluster status
            }
        )
        
        # Ensure cluster is created and data is uploaded before running loader
        data_loader.node.add_dependency(self.dsql_cluster)
        data_loader.node.add_dependency(sample_data_deployment)

        # Outputs
        CfnOutput(
            self, "ClusterIdentifier",
            value=self.dsql_cluster.attr_identifier,
            description="Aurora DSQL Cluster Identifier"
        )
        
        CfnOutput(
            self, "ClusterEndpoint", 
            value=f"{self.dsql_cluster.attr_identifier}.dsql.{self.region}.on.aws",
            description="Aurora DSQL Cluster Endpoint"
        )
        
        CfnOutput(
            self, "DataBucket",
            value=data_bucket.bucket_name,
            description="S3 bucket containing sample data"
        )
