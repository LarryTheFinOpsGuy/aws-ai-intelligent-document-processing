#!/usr/bin/env python3
"""
AgenticIDP Destroy Script

Destroys all CDK stacks in reverse order.
"""
import subprocess
import sys
import argparse


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
        description='Destroy AgenticIDP application stacks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python destroy.py                   # Destroy all stacks
  python destroy.py --force           # Skip confirmation prompts
        """
    )
    parser.add_argument(
        '--force', 
        action='store_true',
        help='Skip confirmation prompts'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("  AgenticIDP Stack Destruction")
    print("="*60)
    
    if not args.force:
        response = input("\n⚠️  This will destroy ALL AgenticIDP stacks. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
    
    # Destroy all stacks - build command with validated inputs only
    if args.force:
        cdk_cmd = ['cdk', 'destroy', '--all', '--force']
    else:
        cdk_cmd = ['cdk', 'destroy', '--all']
    
    run_command(
        cdk_cmd,
        description="Destroying all CDK stacks"
    )
    
    print("\n" + "="*60)
    print("  ✅ All stacks destroyed successfully")
    print("="*60)


if __name__ == "__main__":
    main()
