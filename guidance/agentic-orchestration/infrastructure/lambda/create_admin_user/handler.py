"""
Custom Resource Lambda to create admin user and update Cognito configuration.
Runs after CloudFront distribution is created.

When using CDK's cr.Provider, the handler should:
- Return a dict with response data on success
- Raise an exception on failure
The Provider framework handles CloudFormation responses automatically.
"""
import boto3

cognito_client = boto3.client('cognito-idp')


def handler(event, context):
    """Handle CloudFormation custom resource lifecycle"""
    request_type = event['RequestType']
    properties = event['ResourceProperties']
    
    if request_type == 'Delete':
        # Don't delete user on stack deletion
        return {'Message': 'User not deleted on stack deletion'}
    
    # Get parameters
    user_pool_id = properties['UserPoolId']
    app_client_id = properties['AppClientId']
    admin_email = properties['AdminEmail']
    cloudfront_url = properties.get('CloudFrontUrl', '')
    
    if request_type in ['Create', 'Update']:
        # Update callback URLs if CloudFront URL provided
        if cloudfront_url:
            cognito_client.update_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=app_client_id,
                CallbackURLs=[
                    "http://localhost:3000",
                    "http://localhost:5173",
                    cloudfront_url,
                    f"{cloudfront_url}/callback"
                ],
                LogoutURLs=[
                    "http://localhost:3000",
                    "http://localhost:5173",
                    cloudfront_url
                ],
                AllowedOAuthFlows=['code', 'implicit'],
                AllowedOAuthScopes=['email', 'openid', 'profile', 'aws.cognito.signin.user.admin'],
                AllowedOAuthFlowsUserPoolClient=True,
                SupportedIdentityProviders=['COGNITO']
            )
            
            # Update invitation email template
            user_pool_config = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
            cognito_client.update_user_pool(
                UserPoolId=user_pool_id,
                Policies=user_pool_config['UserPool']['Policies'],
                AdminCreateUserConfig={
                    'InviteMessageTemplate': {
                        'EmailSubject': 'Welcome to AgenticIDP - Your Account Details',
                        'EmailMessage': f'''<p>Hello {{username}},</p>

<p>Welcome to AgenticIDP! Your administrator has created an account for you.</p>

<p><strong>Login Details:</strong></p>
<ul>
  <li>Application URL: <a href="{cloudfront_url}">{cloudfront_url}</a></li>
  <li>Username: {{username}}</li>
  <li>Temporary Password: {{####}}</li>
</ul>

<p>You will be required to change your password when you first sign in.</p>

<p>If you have any questions, please contact your administrator.</p>'''
                    }
                }
            )
        
        # Create admin user
        username = admin_email.split('@')[0]
        try:
            cognito_client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=[
                    {'Name': 'email', 'Value': admin_email},
                    {'Name': 'email_verified', 'Value': 'true'}
                ]
            )
            message = f"Admin user created: {username}"
            print(f"✅ Successfully created admin user for {admin_email} (username: {username})")
        except cognito_client.exceptions.UsernameExistsException:
            message = f"Admin user already exists: {username}"
            print(f"ℹ️  Admin user already exists for {admin_email} (username: {username})")
        
        # Return data - Provider framework handles CloudFormation response
        return {
            'Message': message,
            'Username': username,
            'Email': admin_email
        }
