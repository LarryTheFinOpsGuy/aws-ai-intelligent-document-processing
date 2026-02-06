from constructs import Construct
from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_logs as logs,
    custom_resources as cr,
    CustomResource,
    Duration,
    RemovalPolicy,
    Stack
)
from cdk_nag import NagSuppressions

class S3BucketsConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        app_name = config.get("app_name", "agenticidp")
        account_id = Stack.of(self).account
        
        # Access logs bucket for server access logging
        access_logs_bucket_name = f"{app_name}-access-logs-{account_id}"
        access_logs_bucket = s3.Bucket(
            self, "AccessLogsBucket",
            bucket_name=access_logs_bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True
        )
        
        # Document storage bucket
        document_bucket_name = f"{app_name}-objects-{account_id}"
        self.document_bucket = s3.Bucket(
            self, "DocumentBucket",
            bucket_name=document_bucket_name,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=True,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.PUT, s3.HttpMethods.POST],
                allowed_origins=["*"],
                allowed_headers=["*"]
            )],
            enforce_ssl=True,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="document-bucket-logs/"
        )
        
        # S3 Vectors bucket (custom resource)
        vector_bucket_name = f"{app_name}-vectors-{account_id}"
        
        # IAM role for custom resource
        custom_resource_role = iam.Role(
            self, "S3VectorCustomResourceRole",
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
                                f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/*"
                            ]
                        )
                    ]
                ),
                "S3VectorsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3vectors:CreateVectorBucket",
                                "s3vectors:DeleteVectorBucket",
                                "s3vectors:ListVectorBuckets",
                                "s3vectors:CreateIndex",
                                "s3vectors:DeleteIndex",
                                "s3vectors:ListIndexes"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # CDK Nag suppressions for IAM5 wildcards - applied to role and its policies
        NagSuppressions.add_resource_suppressions(
            custom_resource_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda CloudWatch Logs requires wildcard for dynamic log group creation.",
                    "appliesTo": ["Resource::arn:aws:logs:<AWS::Region>:<AWS::AccountId>:log-group:/aws/lambda/*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "S3 Vectors service requires wildcard permissions for bucket and index management.",
                    "appliesTo": ["Resource::*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK Provider Framework requires Lambda invoke permissions for custom resource handlers.",
                    "appliesTo": ["Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK custom resource provider requires wildcard for Lambda function version management.",
                    "appliesTo": ["Resource::<S3BucketsS3VectorsHandler3EB53BE1.Arn>:*"]
                }
            ],
            apply_to_children=True
        )
        
        # Custom resource provider
        provider_log_group = logs.LogGroup(
            self, "S3VectorsProviderLogGroup",
            log_group_name=f"/aws/lambda/{app_name}-s3vectors-provider",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Create custom role for the provider framework
        provider_role = iam.Role(
            self, "S3VectorsProviderRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "InvokeLambda": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["lambda:InvokeFunction"],
                            resources=[f"arn:aws:lambda:{Stack.of(self).region}:{Stack.of(self).account}:function:*"]
                        )
                    ]
                )
            }
        )
        
        # CDK Nag suppressions for provider role
        NagSuppressions.add_resource_suppressions(
            provider_role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWSLambdaBasicExecutionRole is AWS required managed policy for Lambda CloudWatch logging.",
                    "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK Provider framework requires Lambda invoke wildcard for custom resource handler invocation.",
                    "appliesTo": ["Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*"]
                }
            ],
            apply_to_children=True
        )
        
        s3_vectors_provider = cr.Provider(
            self, "S3VectorsProvider",
            on_event_handler=self._create_s3_vectors_handler(custom_resource_role),
            log_group=provider_log_group,
            role=provider_role
        )
        
        # CDK Nag suppression for Provider framework-onEvent role
        NagSuppressions.add_resource_suppressions(
            s3_vectors_provider,
            [{"id": "AwsSolutions-IAM5", "reason": "CDK Provider framework requires wildcard permissions for Lambda version management.", "appliesTo": ["Resource::<S3BucketsS3VectorsHandler3EB53BE1.Arn>:*"]}],
            apply_to_children=True
        )
        
        # S3 Vectors bucket custom resource
        self.vector_bucket = CustomResource(
            self, "VectorBucket",
            service_token=s3_vectors_provider.service_token,
            properties={
                "VectorBucketName": vector_bucket_name,
                "IndexName": "documentsimilarity",
                "Dimension": 1024,
                "DistanceMetric": "cosine",
                "DataType": "float32",
                "NonFilterableMetadataKeys": ["example_document_uri", "processing_workflow", "notes"]
            }
        )
        
        self.vector_bucket_name = vector_bucket_name
    
    def _create_s3_vectors_handler(self, role: iam.Role):
        from aws_cdk import aws_lambda as lambda_
        
        handler = lambda_.Function(
            self, "S3VectorsHandler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            role=role,
            timeout=Duration.minutes(5),
            code=lambda_.Code.from_inline("""
import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Event: {json.dumps(event)}")
    
    request_type = event['RequestType']
    properties = event['ResourceProperties']
    vector_bucket_name = properties['VectorBucketName']
    index_name = properties.get('IndexName', 'documentsimilarity')
    dimension = int(properties.get('Dimension', 1024))
    distance_metric = properties.get('DistanceMetric', 'cosine')
    data_type = properties.get('DataType', 'float32')
    non_filterable_keys = properties.get('NonFilterableMetadataKeys', [])
    
    try:
        s3vectors_client = boto3.client('s3vectors')
        
        if request_type == 'Create':
            logger.info(f"Creating S3 Vectors bucket: {vector_bucket_name}")
            
            # Create vector bucket
            try:
                s3vectors_client.create_vector_bucket(vectorBucketName=vector_bucket_name)
                logger.info(f"Created vector bucket: {vector_bucket_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"Vector bucket already exists: {vector_bucket_name}")
                else:
                    raise e
            
            # Create vector index
            try:
                create_index_params = {
                    'vectorBucketName': vector_bucket_name,
                    'indexName': index_name,
                    'dimension': dimension,
                    'distanceMetric': distance_metric,
                    'dataType': data_type
                }
                
                if non_filterable_keys:
                    create_index_params['metadataConfiguration'] = {
                        'nonFilterableMetadataKeys': non_filterable_keys
                    }
                
                s3vectors_client.create_index(**create_index_params)
                logger.info(f"Created vector index: {index_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"Vector index already exists: {index_name}")
                else:
                    raise e
            
            return {
                'Status': 'SUCCESS',
                'PhysicalResourceId': vector_bucket_name,
                'Data': {
                    'VectorBucketName': vector_bucket_name,
                    'IndexName': index_name
                }
            }
            
        elif request_type == 'Delete':
            logger.info(f"Deleting S3 Vectors index: {index_name} from bucket: {vector_bucket_name}")
            try:
                # Delete index first
                try:
                    s3vectors_client.delete_index(
                        vectorBucketName=vector_bucket_name,
                        indexName=index_name
                    )
                    logger.info(f"Deleted vector index: {index_name}")
                except Exception as e:
                    logger.warning(f"Error deleting vector index: {e}")
                
                # Then delete bucket
                try:
                    s3vectors_client.delete_vector_bucket(vectorBucketName=vector_bucket_name)
                    logger.info(f"Deleted vector bucket: {vector_bucket_name}")
                except Exception as e:
                    logger.warning(f"Error deleting vector bucket: {e}")
                    
            except Exception as e:
                logger.warning(f"Error during deletion: {e}")
                # Return success anyway to allow stack deletion
            
            return {
                'Status': 'SUCCESS',
                'PhysicalResourceId': vector_bucket_name
            }
            
        elif request_type == 'Update':
            return {
                'Status': 'SUCCESS',
                'PhysicalResourceId': vector_bucket_name,
                'Data': {
                    'VectorBucketName': vector_bucket_name,
                    'IndexName': index_name
                }
            }
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'Status': 'FAILED',
            'Reason': str(e),
            'PhysicalResourceId': vector_bucket_name
        }
""")
        )
        NagSuppressions.add_resource_suppressions(
            handler,
            [{"id": "AwsSolutions-L1", "reason": "Using Python 3.13, the latest available Lambda runtime as of January 2026."}]
        )
        return handler
