#!/usr/bin/env python3
"""
CDK Stack for Modern Orchestrator UI hosting infrastructure.
Creates S3 bucket and CloudFront distribution for the React application.
"""

from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
)
from cdk_nag import NagSuppressions
from constructs import Construct
from infrastructure.components.admin_user_creator import AdminUserCreator


class ModernOrchestratorUIStack(Stack):
    """Stack for Modern Orchestrator UI hosting infrastructure."""

    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        config: dict,
        cognito_user_pool_id: str = None,
        cognito_app_client_id: str = None,
        admin_email: str = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, stack_name=f"AgenticIDP-{construct_id}", **kwargs)
        
        self.app_name = config.get("app_name", "agenticidp")
        self.env_name = config.get("environment", "dev")  # Renamed to avoid conflict
        account_id = Stack.of(self).account
        
        # Create CloudFront access logs bucket
        # Reference Core stack's access logs bucket for S3 server access logs
        self.access_logs_bucket = s3.Bucket.from_bucket_name(
            self, "AccessLogsBucket",
            f"{self.app_name}-access-logs-{account_id}"
        )
        
        self.cloudfront_logs_bucket = s3.Bucket(
            self, "CloudFrontLogsBucket",
            bucket_name=f"{self.app_name}-cloudfront-logs-{account_id}",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,  # Enable ACLs for CloudFront
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="cloudfront-logs-bucket/"
        )
        
        # Create S3 bucket for web assets
        self.web_bucket = self._create_web_bucket()
        
        # Create CloudFront distribution
        self.distribution = self._create_cloudfront_distribution()
        
        # Create admin user if email provided
        if admin_email and cognito_user_pool_id and cognito_app_client_id:
            cloudfront_url = f"https://{self.distribution.distribution_domain_name}"
            self.admin_user_creator = AdminUserCreator(
                self, "AdminUserCreator",
                user_pool_id=cognito_user_pool_id,
                app_client_id=cognito_app_client_id,
                admin_email=admin_email,
                cloudfront_url=cloudfront_url
            )
        
        # Create outputs
        self._create_outputs()

    def _create_web_bucket(self) -> s3.Bucket:
        """Create S3 bucket for hosting the React application."""
        
        account_id = Stack.of(self).account
        
        bucket = s3.Bucket(
            self,
            "ModernOrchestratorUIBucket",
            bucket_name=f"{self.app_name}-modern-orchestrator-ui-{self.env_name}-{account_id}",
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            enforce_ssl=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="modern-ui/",
            cors=[
                s3.CorsRule(
                    allowed_headers=["*"],
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.HEAD,
                    ],
                    allowed_origins=["*"],
                    exposed_headers=["ETag"],
                    max_age=3000
                )
            ]
        )
        
        return bucket

    def _create_cloudfront_distribution(self) -> cloudfront.Distribution:
        """Create CloudFront distribution for the React application."""
        
        # CloudFront distribution with OAC
        distribution = cloudfront.Distribution(
            self,
            "ModernOrchestratorUIDistributionV2",  # Changed ID to force replacement
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(self.web_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                compress=True,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                )
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            enable_logging=True,
            log_bucket=self.cloudfront_logs_bucket,
            log_file_prefix="cloudfront/",            
            comment=f"CloudFront distribution for {self.app_name} Modern Orchestrator UI"
        )
        
        # CDK Nag suppressions for demo/guidance application
        NagSuppressions.add_resource_suppressions(
            distribution,
            [
                {
                    "id": "AwsSolutions-CFR1",
                    "reason": "Demo/guidance application. Geo restrictions not required for global demo access."
                },
                {
                    "id": "AwsSolutions-CFR2",
                    "reason": "Demo/guidance application. WAF integration adds cost and complexity not needed for demo purposes."
                },
                {
                    "id": "AwsSolutions-CFR4",
                    "reason": "Demo/guidance application. Custom certificate with TLS 1.2+ requires a custom domain. Using CloudFront default certificate which enforces TLS 1.0 minimum per AWS design."
                }
            ]
        )
        
        return distribution

    def _create_outputs(self):
        """Create stack outputs."""
        
        CfnOutput(
            self, "WebsiteURL",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="Modern Orchestrator UI Website URL"
        )
        
        CfnOutput(
            self, "WebBucketName",
            value=self.web_bucket.bucket_name,
            description="S3 bucket name for Modern Orchestrator UI web assets"
        )
        
        CfnOutput(
            self, "DistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID for Modern Orchestrator UI"
        )
        
        CfnOutput(
            self, "DistributionDomainName",
            value=self.distribution.distribution_domain_name,
            description="CloudFront distribution domain name"
        )
        
        CfnOutput(
            self, "BucketArn",
            value=self.web_bucket.bucket_arn,
            description="S3 bucket ARN for Modern Orchestrator UI"
        )