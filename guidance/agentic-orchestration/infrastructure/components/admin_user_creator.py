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
