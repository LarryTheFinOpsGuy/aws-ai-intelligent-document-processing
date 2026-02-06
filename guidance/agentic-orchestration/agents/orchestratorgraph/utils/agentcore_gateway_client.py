from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import boto3
import os
import logging

logger = logging.getLogger(__name__)

class MCPClientManager:
    _instance = None
    _client = None
    _config = None
    _tools = None
    _global_context_active = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config = self._get_config_from_parameter_store()
    
    def _get_config_from_parameter_store(self) -> dict:
        """Get all configuration parameters from Parameter Store."""
        try:
            param_path = os.getenv('CONFIG_PARAMETER_PATH', '/agenticidp/dev')
            ssm = boto3.client('ssm')
            
            response = ssm.get_parameters_by_path(
                Path=param_path,
                Recursive=True,
                WithDecryption=True
            )
            
            config = {}
            for param in response['Parameters']:
                key = param['Name'].split('/')[-1]
                config[key] = param['Value']
                logger.debug(f"Parameter: {key} = {param['Value']}")
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load parameters from {param_path}: {e}")
            return {}
    
    def _get_gateway_access_token(self):
        @requires_access_token(
            provider_name=self._config.get('provider-name'),
            scopes=[self._config.get('provider-scopes')],
            auth_flow="M2M",
            force_authentication=False,
        )
        def _inner(access_token: str):
            return access_token
        return _inner()
    
    def get_client(self):
        if self._client is None:
            access_token = self._get_gateway_access_token()
            gateway_url = self._config.get('gateway-url')
            self._client = MCPClient(
                lambda: streamablehttp_client(
                    gateway_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
            )
        return self._client
    
    def activate_global_context(self):
        """Activate global MCP client context"""
        if not self._global_context_active:
            client = self.get_client()
            client.__enter__()
            self._global_context_active = True
            logger.info("Global MCP client context activated")
    
    def deactivate_global_context(self):
        """Deactivate global MCP client context"""
        if self._global_context_active and self._client:
            self._client.__exit__(None, None, None)
            self._global_context_active = False
            logger.info("Global MCP client context deactivated")
    
    def get_client_context(self):
        """Return client ready for use in context manager"""
        return self.get_client()
    
    def get_tools_with_context(self):
        """Get tools and return both tools and client for context management"""
        client = self.get_client()
        with client:
            tools = client.list_tools_sync()
        return tools, client
    
    def get_tools(self):
        """Get tools once and cache them"""
        if self._tools is None:
            client = self.get_client()
            if self._global_context_active:
                # Context already active, just get tools
                self._tools = client.list_tools_sync()
            else:
                # Need to enter context temporarily
                with client:
                    self._tools = client.list_tools_sync()
            logger.info(f"Cached {len(self._tools)} MCP tools")
        return self._tools
    
    def get_tool_by_name(self, tool_name: str):
        """Get specific tool by name"""
        tools = self.get_tools()
        return next((tool for tool in tools if tool.tool_name == tool_name), None)

# Global singleton instance
mcp_manager = MCPClientManager()
