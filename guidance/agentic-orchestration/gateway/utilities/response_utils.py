"""Shared response formatting utilities for all gateway tools."""
import json
from typing import Any, Dict, Tuple

def create_error_response(message: str, status_code: int = 400) -> Dict[str, Any]:
    """Standard error response format for gateway compatibility."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Session-Id,X-Request-Id",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS"
        },
        "body": json.dumps({
            "error": message,
            "success": False
        })
    }

def create_success_response(data: Any, status_code: int = 200) -> Dict[str, Any]:
    """Standard success response format for gateway compatibility."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Session-Id,X-Request-Id",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS"
        },
        "body": json.dumps(data) if isinstance(data, dict) else data
    }

def parse_lambda_event(event: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Parse Lambda event to extract tool name and parameters."""
    if 'toolName' in event:
        # Direct invocation format
        return event.get('toolName'), event.get('parameters', {})
    else:
        # Gateway format - return None for tool name, full event as parameters
        return None, event
