import json
import boto3
import cfnresponse
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        agentcore_client = boto3.client('bedrock-agentcore-control')
        cognito_client = boto3.client('cognito-idp')
        
        request_type = event['RequestType']
        properties = event['ResourceProperties']
        
        provider_name = properties['ProviderName']
        logger.info(f"Processing {request_type} for provider: {provider_name}")
        
        if request_type == 'Create':
            # Get client secret from Cognito
            user_pool_id = properties['UserPoolId']
            client_id = properties['ClientId']
            
            client_details = cognito_client.describe_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            
            client_secret = client_details['UserPoolClient'].get('ClientSecret')
            if not client_secret:
                raise Exception("App client does not have a secret")
            
            # Check if provider already exists
            try:
                existing_provider = agentcore_client.get_oauth2_credential_provider(name=provider_name)
                provider_arn = existing_provider['credentialProviderArn']
                logger.info(f"Provider {provider_name} already exists with ARN: {provider_arn}")
                
                # Return success with existing provider
                cfnresponse.send(
                    event, 
                    context, 
                    cfnresponse.SUCCESS, 
                    {'ProviderArn': provider_arn},
                    physicalResourceId=provider_name
                )
                return
            except agentcore_client.exceptions.ResourceNotFoundException:
                # Provider doesn't exist, create it
                logger.info(f"Provider {provider_name} not found, creating new one")
            
            oauth2_config = {
                "customOauth2ProviderConfig": {
                    "oauthDiscovery": {
                        "discoveryUrl": properties['DiscoveryUrl']
                    },
                    "clientId": client_id,
                    "clientSecret": client_secret
                }
            }
            
            response = agentcore_client.create_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor="CustomOauth2",
                oauth2ProviderConfigInput=oauth2_config
            )
            
            provider_arn = response['credentialProviderArn']
            logger.info(f"Successfully created provider with ARN: {provider_arn}")
            
            # Send response with physical resource ID set to provider name
            # This ensures CloudFormation can track the resource for deletion
            cfnresponse.send(
                event, 
                context, 
                cfnresponse.SUCCESS, 
                {'ProviderArn': provider_arn},
                physicalResourceId=provider_name
            )
                    
        elif request_type == 'Update':
            # For updates, we need to check if the provider name changed
            old_provider_name = event.get('PhysicalResourceId', provider_name)
            
            if old_provider_name != provider_name:
                # Provider name changed - delete old and create new
                logger.info(f"Provider name changed from {old_provider_name} to {provider_name}")
                try:
                    agentcore_client.delete_oauth2_credential_provider(name=old_provider_name)
                    logger.info(f"Deleted old provider: {old_provider_name}")
                except Exception as e:
                    logger.warning(f"Failed to delete old provider: {str(e)}")
                
                # Create new provider
                user_pool_id = properties['UserPoolId']
                client_id = properties['ClientId']
                
                client_details = cognito_client.describe_user_pool_client(
                    UserPoolId=user_pool_id,
                    ClientId=client_id
                )
                
                client_secret = client_details['UserPoolClient'].get('ClientSecret')
                if not client_secret:
                    raise Exception("App client does not have a secret")
                
                oauth2_config = {
                    "customOauth2ProviderConfig": {
                        "oauthDiscovery": {
                            "discoveryUrl": properties['DiscoveryUrl']
                        },
                        "clientId": client_id,
                        "clientSecret": client_secret
                    }
                }
                
                response = agentcore_client.create_oauth2_credential_provider(
                    name=provider_name,
                    credentialProviderVendor="CustomOauth2",
                    oauth2ProviderConfigInput=oauth2_config
                )
                
                provider_arn = response['credentialProviderArn']
                logger.info(f"Created new provider with ARN: {provider_arn}")
                
                cfnresponse.send(
                    event,
                    context,
                    cfnresponse.SUCCESS,
                    {'ProviderArn': provider_arn},
                    physicalResourceId=provider_name
                )
            else:
                # No name change - OAuth2 providers are immutable, so no update needed
                logger.info(f"No changes to provider {provider_name}")
                cfnresponse.send(
                    event,
                    context,
                    cfnresponse.SUCCESS,
                    {},
                    physicalResourceId=provider_name
                )
        
        elif request_type == 'Delete':
            try:
                # Delete the OAuth2 credential provider
                agentcore_client.delete_oauth2_credential_provider(name=provider_name)
                logger.info(f"Successfully deleted provider: {provider_name}")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            except agentcore_client.exceptions.ResourceNotFoundException:
                logger.info(f"Provider {provider_name} not found, already deleted")
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            except Exception as e:
                logger.error(f"Failed to delete provider {provider_name}: {str(e)}")
                # Send SUCCESS anyway to allow stack deletion to proceed
                # The resource may have been manually deleted or doesn't exist
                cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                    'Warning': f'Delete failed but continuing: {str(e)}'
                })
        
        else:
            logger.info(f"No action needed for request type: {request_type}")
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        cfnresponse.send(event, context, cfnresponse.FAILED, {'Error': str(e)})
