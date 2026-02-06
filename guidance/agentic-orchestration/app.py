#!/usr/bin/env python3
import aws_cdk as cdk
from infrastructure.stacks.core_stack import CoreStack
from infrastructure.stacks.agent_stack import AgentStack
from infrastructure.stacks.gateway_stack import GatewayStack
from infrastructure.stacks.aurora_stack import AuroraStack
from infrastructure.stacks.ui.ui_orchestrator_stack import UIOrchestratorStack
from infrastructure.stacks.ui.modern_orchestrator_ui_stack import ModernOrchestratorUIStack
from cdk_nag import AwsSolutionsChecks, HIPAASecurityChecks, NagSuppressions, NagPackSuppression


app = cdk.App()

cdk.Stack(app, "MyStack",
    description="My solution description (uksb-wxpa92o82g)."
)

# Get configuration from context
config = app.node.try_get_context("agenticidp")
env_name = app.node.try_get_context("agenticidp:environment") or "development"

env_config = config.get(env_name, config["development"]) if config else {
    "environment": "dev",
    "app_name": "agenticidp"
}

# 1. Core infrastructure stack
core_stack = CoreStack(
    app, 
    f"Core-{env_config['environment'].title()}",
    config=env_config
)

# 2. Aurora DSQL stack
aurora_stack = AuroraStack(
    app,
    f"Aurora-{env_config['environment'].title()}",
    config=env_config
)

# 3. Gateway stack (includes Lambda functions and Bedrock AgentCore Gateway)
gateway_stack = GatewayStack(
    app,
    f"Gateway-{env_config['environment'].title()}",
    config=env_config,
    core_stack=core_stack,
    aurora_stack=aurora_stack
)

# 4. Agent stack (Bedrock AgentCore Runtime + Automation)
agent_stack = AgentStack(
    app,
    f"Agent-{env_config['environment'].title()}",
    config=env_config,
    core_stack=core_stack
)

# 5. Modern Orchestrator UI API stack (API Gateway for React app)
ui_orchestrator_stack = UIOrchestratorStack(
    app,
    f"UIOrchestr-{env_config['environment'].title()}",
    config=env_config,
    core_stack=core_stack,
    agent_stack=agent_stack,
    gateway_stack=gateway_stack
)

# 6. Modern Orchestrator UI Hosting stack (S3 + CloudFront for React SPA)
# Get admin email from context (CLI) or environment config (cdk.context.json)
admin_email = app.node.try_get_context("admin_email") or env_config.get("admin_email")

modern_ui_stack = ModernOrchestratorUIStack(
    app,
    f"ModernUI-{env_config['environment'].title()}",
    config=env_config,
    cognito_user_pool_id=core_stack.cognito.user_pool.user_pool_id if admin_email else None,
    cognito_app_client_id=core_stack.cognito.web_app_client.user_pool_client_id if admin_email else None,
    admin_email=admin_email
)

# Set dependencies
ui_orchestrator_stack.add_dependency(core_stack)
ui_orchestrator_stack.add_dependency(agent_stack)
ui_orchestrator_stack.add_dependency(gateway_stack)
modern_ui_stack.add_dependency(ui_orchestrator_stack)  # UI hosting depends on API stack

# Apply CDK Nag checks with report generation
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True, reports=True))

app.synth()
