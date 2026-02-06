from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    Tags,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_ssm as ssm
)
from cdk_nag import NagSuppressions
from infrastructure.components.s3_buckets import S3BucketsConstruct
from infrastructure.components.cognito_auth import CognitoAuthConstruct

class CoreStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, stack_name=f"AgenticIDP-{construct_id}", **kwargs)
        
        app_name = config.get("app_name", "agenticidp")
        
        # S3 buckets (document and vector)
        self.s3_buckets = S3BucketsConstruct(
            self, "S3Buckets",
            config=config
        )
        
        # Cognito authentication
        self.cognito = CognitoAuthConstruct(
            self, "CognitoAuth",
            config=config
        )
        
        # DynamoDB table for processing jobs
        self.processing_jobs_table = dynamodb.Table(
            self, "ProcessingJobsTable",
            table_name="processing-jobs",
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )
        
        # GSI1: sender_name + created_at
        self.processing_jobs_table.add_global_secondary_index(
            index_name="sender_name-created_at-index",
            partition_key=dynamodb.Attribute(
                name="sender_name",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            )
        )
        
        # GSI2: doc_type + created_at
        self.processing_jobs_table.add_global_secondary_index(
            index_name="doc_type-created_at-index",
            partition_key=dynamodb.Attribute(
                name="doc_type",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            )
        )
        
        # GSI3: status + created_at (for recent jobs by status)
        self.processing_jobs_table.add_global_secondary_index(
            index_name="status-created_at-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at",
                type=dynamodb.AttributeType.STRING
            )
        )
        
        # DynamoDB table for processing actions
        self.processing_actions_table = dynamodb.Table(
            self, "ProcessingActionsTable",
            table_name="processing-actions",
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="started_at",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True
        )
        
        # GSI1: agent + started_at
        self.processing_actions_table.add_global_secondary_index(
            index_name="agent-started_at-index",
            partition_key=dynamodb.Attribute(
                name="agent",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="started_at",
                type=dynamodb.AttributeType.STRING
            )
        )
        
        # Stack outputs
        CfnOutput(
            self, "DocumentBucketName",
            value=self.s3_buckets.document_bucket.bucket_name,
            description="S3 bucket for document storage"
        )
        
        CfnOutput(
            self, "VectorBucketName", 
            value=self.s3_buckets.vector_bucket_name,
            description="S3 Vectors bucket for embeddings"
        )
        
        CfnOutput(
            self, "ProcessingJobsTableName",
            value=self.processing_jobs_table.table_name,
            description="DynamoDB table for processing jobs"
        )
        
        CfnOutput(
            self, "ProcessingActionsTableName",
            value=self.processing_actions_table.table_name,
            description="DynamoDB table for processing actions"
        )
        
        # Create SSM parameters for DynamoDB table names
        ssm.StringParameter(
            self, "ProcessingJobsTableNameParameter",
            parameter_name=f"/{app_name.lower()}/agents/processing_jobs_table_name",
            string_value=self.processing_jobs_table.table_name,
            description="DynamoDB table name for processing jobs"
        )
        
        ssm.StringParameter(
            self, "ProcessingActionsTableNameParameter",
            parameter_name=f"/{app_name.lower()}/agents/processing_actions_table_name",
            string_value=self.processing_actions_table.table_name,
            description="DynamoDB table name for processing actions"
        )
        
        # Add tags
        Tags.of(self).add("Project", "AgenticIDP")
        Tags.of(self).add("Environment", config["environment"])
        Tags.of(self).add("ManagedBy", "CDK")
        
        # Add CDK Nag suppressions for auto-generated handlers
        NagSuppressions.add_stack_suppressions(self, [
            {
                "id": "AwsSolutions-IAM4",
                "reason": "BucketNotificationsHandler is auto-generated by CDK for S3 EventBridge integration. CDK manages this role and uses AWSLambdaBasicExecutionRole for the internal Lambda function.",
                "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
            },
            {
                "id": "AwsSolutions-IAM4",
                "reason": "CDK Custom::S3AutoDeleteObjects handler uses AWSLambdaBasicExecutionRole managed by CDK framework."
            },
            {
                "id": "AwsSolutions-IAM5",
                "reason": "CDK Custom::S3AutoDeleteObjects requires wildcard permissions for bucket deletion operations."
            },
            {
                "id": "AwsSolutions-L1",
                "reason": "Lambda runtime version controlled by CDK framework for Custom::S3AutoDeleteObjects handler."
            },
            {
                "id": "AwsSolutions-IAM4",
                "reason": "CDK Provider framework uses AWSLambdaBasicExecutionRole for custom resource handlers."
            },
            {
                "id": "AwsSolutions-IAM5",
                "reason": "CDK Provider framework requires wildcard permissions for Lambda function version management."
            }
        ])
