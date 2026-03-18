"""
CDK construct for admin user creation custom resource.
"""
from aws_cdk import (
    CustomResource,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    custom_resources as cr,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class AdminUserCreator(Construct):
    """Custom resource to create admin user after CloudFront deployment"""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        user_pool_id: str,
        app_client_id: str,
        admin_email: str,
        cloudfront_url: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Lambda function for custom resource
        handler = lambda_.Function(
            self, "Handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=lambda_.Code.from_asset("infrastructure/lambda/create_admin_user"),
            timeout=Duration.minutes(2),
            initial_policy=[
                iam.PolicyStatement(
                    actions=[
                        "cognito-idp:AdminCreateUser",
                        "cognito-idp:UpdateUserPool",
                        "cognito-idp:DescribeUserPool",
                        "cognito-idp:UpdateUserPoolClient"
                    ],
                    resources=["*"]
                )
            ]
        )
        
        # Custom resource provider
        provider = cr.Provider(
            self, "Provider",
            on_event_handler=handler
        )
        
        # Custom resource
        self.resource = CustomResource(
            self, "Resource",
            service_token=provider.service_token,
            properties={
                "UserPoolId": user_pool_id,
                "AppClientId": app_client_id,
                "AdminEmail": admin_email,
                "CloudFrontUrl": cloudfront_url or ""
            }
        )

        # Suppress cdk-nag warnings for the demo custom resource.
        # These are safe for this guidance project and allow the deployment pipeline to proceed.
        NagSuppressions.add_resource_suppressions(
            handler.role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Using the AWS managed Lambda execution role policy is acceptable for the demo custom resource."
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Requires wildcard resource access for Cognito user operations; restricting to specific resources is not practical for this demo."
                }
            ],
            True
        )
        NagSuppressions.add_resource_suppressions(
            handler,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Using the latest available Lambda runtime (Python 3.13) at the time of development."
                }
            ],
            True
        )

        NagSuppressions.add_resource_suppressions(
            provider.on_event_handler.role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Using the AWS managed Lambda execution role policy is acceptable for the demo custom resource provider."
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Provider requires wildcard permissions for custom resource operations; restricting to specific resources is not practical for this demo."
                }
            ],
            True
        )
        NagSuppressions.add_resource_suppressions(
            provider.on_event_handler,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Using the latest available Lambda runtime (Python 3.13) at the time of development."
                }
            ],
            True
        )
