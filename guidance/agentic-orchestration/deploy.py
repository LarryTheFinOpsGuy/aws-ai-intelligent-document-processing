#!/usr/bin/env python3
"""
AgenticIDP Deployment Script

Handles two-phase deployment:
1. Deploy CDK stacks (Core, UI Orchestrator, UI infrastructure)
2. Build and deploy UI with CloudFormation outputs
"""
import subprocess
import sys
import argparse
import json
import os


def load_context():
    """Load CDK context configuration"""
    context_file = "cdk.context.json"
    if not os.path.exists(context_file):
        print(f"❌ Error: {context_file} not found")
        sys.exit(1)
    
    with open(context_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_admin_email(env, admin_email_arg):
    """Check if admin_email is configured, prompt if missing"""
    context = load_context()
    
    # Map env to context key
    env_key = 'development' if env == 'dev' else 'production'
    
    # Check if admin_email exists in context
    context_email = context.get('agenticidp', {}).get(env_key, {}).get('admin_email', '')
    
    # Use CLI arg if provided, otherwise use context value
    admin_email = admin_email_arg or context_email
    
    # If still empty, prompt user
    if not admin_email:
        print("\n⚠️  Admin email not configured!")
        print(f"   Environment: {env}")
        print(f"   Context file: cdk.context.json")
        print()
        admin_email = input("Enter admin email address: ").strip()
        
        if not admin_email or '@' not in admin_email:
            print("❌ Invalid email address")
            sys.exit(1)
    
    # Validate email format to prevent injection
    if not admin_email or '@' not in admin_email or len(admin_email) > 254:
        print("❌ Invalid email address format")
        sys.exit(1)
    
    # Prevent command injection by checking for shell metacharacters
    dangerous_chars = [';', '&', '|', '$', '`', '\n', '\r', '>', '<', '(', ')', '{', '}']
    if any(char in admin_email for char in dangerous_chars):
        print("❌ Email contains invalid characters")
        sys.exit(1)
    
    return admin_email


def run_command(cmd, cwd=None, description=None):
    """Run command safely without shell interpretation"""
    if description:
        print(f"\n{'='*60}")
        print(f"  {description}")
        print('='*60)
    
    # Ensure cmd is a list for safety
    if isinstance(cmd, str):
        raise ValueError("Command must be a list, not a string. This prevents command injection.")
    
    # Safe: cmd is validated as list, shell=False prevents injection
    # nosemgrep: dangerous-subprocess-use-audit
    result = subprocess.run(cmd, cwd=cwd, shell=False)
    if result.returncode != 0:
        print(f"❌ Failed: {description or ' '.join(cmd)}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Deploy AgenticIDP application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py                                    # Deploy everything to dev
  python deploy.py --env prod                         # Deploy to production
  python deploy.py --skip-ui                          # Deploy only CDK stacks
  python deploy.py --admin-email user@example.com     # Create admin user during deployment
        """
    )
    parser.add_argument(
        '--env', 
        default='dev', 
        choices=['dev', 'prod'], 
        help='Environment to deploy (default: dev)'
    )
    parser.add_argument(
        '--skip-ui', 
        action='store_true',
        help='Skip UI build and deployment'
    )
    parser.add_argument(
        '--admin-email',
        help='Admin email address for initial user creation'
    )
    args = parser.parse_args()
    
    # Check and validate admin email before deployment
    admin_email = check_admin_email(args.env, args.admin_email)
    
    print("\n🚀 AgenticIDP Deployment")
    print(f"Environment: {args.env}")
    print(f"Admin Email: {admin_email}")
    print(f"Skip UI: {args.skip_ui}")
    print()
    
    # Phase 1: Deploy CDK stacks
    cdk_cmd = ["cdk", "deploy", "--all", "--require-approval", "never", "-c", f"admin_email={admin_email}"]
    
    run_command(
        cdk_cmd,
        description="Phase 1: Deploying CDK stacks"
    )
    
    # Phase 2: Build and deploy UI (unless skipped)
    if not args.skip_ui:
        run_command(
            ["npm", "run", f"deploy:cdk:{args.env}"],
            cwd="ui/orchestrator",
            description=f"Phase 2: Building and deploying UI for {args.env}"
        )
    
    print("\n" + "="*60)
    print("  ✅ Deployment Complete!")
    print("="*60)
    
    if not args.skip_ui:
        print("\n📋 To get your application URL:")
        print(f"   aws cloudformation describe-stacks \\")
        print(f"     --stack-name AgenticIDP-ModernUI-Dev \\")
        print(f"     --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \\")
        print(f"     --output text\n")


if __name__ == "__main__":
    main()
