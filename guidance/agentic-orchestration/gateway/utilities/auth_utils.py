"""Shared authentication utilities for all gateway tools."""
import json
import boto3
from typing import Dict, Any, Optional

def validate_gateway_request(event: Dict[str, Any]) -> bool:
    """Validate incoming gateway request format."""
    # Basic validation - in production would check JWT tokens
    return isinstance(event, dict)

def get_request_context(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract request context from gateway event."""
    return {
        "request_id": event.get("requestId", "unknown"),
        "source": "gateway" if "toolName" not in event else "direct"
    }

def log_request(event: Dict[str, Any], context: Any = None) -> None:
    """Log incoming request for debugging."""
    print(event)
    print(context)
