"""Centralized configuration for CDK assets to improve build performance."""

from aws_cdk import aws_ecr_assets as ecr_assets
from typing import List

# Standard exclusion patterns for all Docker assets
STANDARD_DOCKER_EXCLUDES = [
    # Python
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.pyd",
    ".Python",
    "build/**",
    "develop-eggs/**",
    "dist/**",
    "downloads/**",
    "eggs/**",
    ".eggs/**",
    "lib/**",
    "lib64/**",
    "parts/**",
    "sdist/**",
    "var/**",
    "wheels/**",
    "**/*.egg-info/**",
    ".installed.cfg",
    "*.egg",
    
    # Virtual environments
    ".venv/**",
    "venv/**",
    "ENV/**",
    "env/**",
    
    # IDE and editors
    ".vscode/**",
    ".idea/**",
    "*.swp",
    "*.swo",
    "*~",
    
    # OS files
    ".DS_Store",
    "Thumbs.db",
    
    # Git
    ".git/**",
    ".gitignore",
    
    # CDK
    "cdk.out/**",
    ".cdk.staging/**",
    
    # Documentation
    "documentation/**",
    "*.md",
    "README*",
    
    # Test files
    "tests/**",
    "test_*.py",
    "*_test.py",
    
    # Logs
    "logs/**",
    "*.log",
    
    # Jupyter
    "*.ipynb",
    ".ipynb_checkpoints/**",
    
    # Temporary files
    "tmp/**",
    "temp/**",
    "*.tmp",
    
    # Large sample files
    "sample-files/**",
    
    # Node modules and UI development files
    "node_modules/**",
    "ui/orchestrator/**",
    "ui/web-app/**", 
    "ui/vite/**",
    
    # Large media files
    "**/*.csv",
    "**/*.pdf",
    "**/*.png",
    "**/*.jpg",
    "**/*.jpeg",
    "**/*.gif",
    "**/*.mp4",
    "**/*.avi"
]

def get_docker_asset_props(
    directory: str = ".",
    dockerfile: str = "Dockerfile",
    additional_excludes: List[str] = None,
    platform: ecr_assets.Platform = ecr_assets.Platform.LINUX_ARM64
) -> dict:
    """
    Get standardized Docker asset properties with optimized excludes.
    
    Args:
        directory: Build context directory
        dockerfile: Path to Dockerfile
        additional_excludes: Additional patterns to exclude
        platform: Target platform
        
    Returns:
        Dict of properties for ContainerImage.from_asset()
    """
    excludes = STANDARD_DOCKER_EXCLUDES.copy()
    
    if additional_excludes:
        excludes.extend(additional_excludes)
    
    return {
        "directory": directory,
        "file": dockerfile,
        "platform": platform,
        "exclude": excludes
    }

def get_lambda_asset_props(
    directory: str,
    additional_excludes: List[str] = None
) -> dict:
    """
    Get standardized Lambda asset properties with optimized excludes.
    
    Args:
        directory: Source directory
        additional_excludes: Additional patterns to exclude
        
    Returns:
        Dict of properties for Code.from_asset()
    """
    # Lambda-specific excludes (lighter than Docker)
    lambda_excludes = [
        "**/__pycache__/**",
        "**/*.pyc",
        "tests/**",
        "test_*.py",
        "*_test.py",
        "*.md",
        ".git/**",
        ".vscode/**",
        ".idea/**",
        "*.log"
    ]
    
    if additional_excludes:
        lambda_excludes.extend(additional_excludes)
    
    return {
        "path": directory,
        "exclude": lambda_excludes
    }
