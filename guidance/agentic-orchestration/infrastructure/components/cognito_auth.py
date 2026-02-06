import re
from constructs import Construct
from aws_cdk import (
    aws_cognito as cognito,
    aws_ssm as ssm,
    CfnOutput,
    RemovalPolicy,
    Stack
)
from cdk_nag import NagSuppressions

class CognitoAuthConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        app_name = config.get("app_name", "agenticidp")
        account_id = Stack.of(self).account
        
        # User pool
        pool_name = f"{app_name}-gateway-pool"
        self.user_pool = cognito.UserPool(
            self, "GatewayPool",
            user_pool_name=pool_name,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=True
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                given_name=cognito.StandardAttribute(required=False, mutable=True),
                family_name=cognito.StandardAttribute(required=False, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True
            ),
            mfa=cognito.Mfa.OPTIONAL,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            self_sign_up_enabled=False,  # Disable self-registration to suppress deletion warning
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # CDK Nag suppression for IAM5 wildcard
        NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Cognito SMS role requires wildcard SNS publish permission per AWS service design.",
                    "appliesTo": ["Resource::*"]
                }
            ],
            apply_to_children=True
        )
        
        # Resource server for OAuth scopes (existing - for gateway)
        self.resource_server = cognito.UserPoolResourceServer(
            self, "GatewayResourceServer",
            user_pool=self.user_pool,
            identifier=f"{app_name}-gateway",
            user_pool_resource_server_name="AgenticIDPGateway",
            scopes=[
                cognito.ResourceServerScope(
                    scope_name="invoke",
                    scope_description="Invoke gateway"
                )
            ]
        )
        
        # Domain for OAuth endpoints
        domain_name = f"{app_name}-gateway-{account_id}"
        self.domain = cognito.UserPoolDomain(
            self, "GatewayDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_name
            )
        )
        
        # Gateway app client (existing - for service-to-service)
        gateway_client_name = f"{app_name}-gateway-client"
        self.gateway_app_client = cognito.UserPoolClient(
            self, "GatewayClient",
            user_pool=self.user_pool,
            user_pool_client_name=gateway_client_name,
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    client_credentials=True
                ),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        self.resource_server,
                        cognito.ResourceServerScope(
                            scope_name="invoke",
                            scope_description="Invoke gateway"
                        )
                    )
                ]
            ),
            auth_flows=cognito.AuthFlow(
                user_password=True,
                admin_user_password=True
            )
        )
        
        # Web app client (for React web application, no secret)
        web_client_name = f"{app_name}-web-client"
        self.web_app_client = cognito.UserPoolClient(
            self, "WebClient",
            user_pool=self.user_pool,
            user_pool_client_name=web_client_name,
            generate_secret=False,  # Web clients should not have secrets
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                admin_user_password=True
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ],
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                    cognito.OAuthScope.COGNITO_ADMIN
                ],
                callback_urls=[
                    "http://localhost:3000",
                    "http://localhost:3001", 
                    "http://localhost:5173",
                    "https://example.com"
                ],
                logout_urls=[
                    "http://localhost:3000",
                    "http://localhost:3001",
                    "http://localhost:5173", 
                    "https://example.com"
                ]
            )
        )
        
        # SSM Parameters
        ssm.StringParameter(
            self, "UserPoolIdParameter",
            parameter_name=f"/{app_name.lower()}/cognito/user_pool_id",
            string_value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )
        
        # Web client parameters
        ssm.StringParameter(
            self, "WebClientIdParameter",
            parameter_name=f"/{app_name.lower()}/cognito/web_client_id",
            string_value=self.web_app_client.user_pool_client_id,
            description="Cognito Web App Client ID (no secret)"
        )
        
        # Identity Pool for web application
        identity_pool_name = f"{app_name}_web_identity_pool"
        self.identity_pool = cognito.CfnIdentityPool(
            self, "WebIdentityPool",
            identity_pool_name=identity_pool_name,
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.web_app_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name
                )
            ]
        )
        
        # SSM Parameter for Identity Pool
        ssm.StringParameter(
            self, "IdentityPoolIdParameter",
            parameter_name=f"/{app_name.lower()}/cognito/identity_pool_id",
            string_value=self.identity_pool.ref,
            description="Cognito Identity Pool ID"
        )
        
        # CDK Nag suppressions for demo/guidance application
        NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "Demo/guidance application. MFA is optional to simplify testing. Production deployments should set mfa=cognito.Mfa.REQUIRED."
                },
                {
                    "id": "AwsSolutions-COG3",
                    "reason": "Demo/guidance application. Advanced security mode not enforced to reduce costs. Production deployments should enable advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED."
                }
            ]
        )
        
        # Outputs
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolArn", value=self.user_pool.user_pool_arn)
        CfnOutput(self, "GatewayAppClientId", value=self.gateway_app_client.user_pool_client_id)
        CfnOutput(self, "ResourceServerId", value=self.resource_server.user_pool_resource_server_id)
        CfnOutput(self, "DomainName", value=self.domain.domain_name)
        
        # Web client outputs
        CfnOutput(self, "WebAppClientId", value=self.web_app_client.user_pool_client_id)
        CfnOutput(self, "IdentityPoolId", value=self.identity_pool.ref)
