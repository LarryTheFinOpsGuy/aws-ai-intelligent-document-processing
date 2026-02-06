import json
import boto3
import logging
import traceback
from typing import Dict, Any
from textractor import Textractor
from textractor.data.constants import TextractFeatures

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get current region
current_region = boto3.Session().region_name

# Initialize clients
s3_client = boto3.client('s3')

def create_error_response(error_message: str) -> Dict[str, Any]:
    """Create standardized error response."""
    return {
        'statusCode': 400,
        'body': json.dumps({
            'error': error_message,
            'success': False
        })
    }

def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized success response."""
    return {
        'statusCode': 200,
        'body': json.dumps(data)
    }

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main Lambda handler for textractor operations."""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # Extract parameters
        document_uri = event.get('document_uri')
        output_format = event.get('output_format', 'markdown')  # Default to markdown
        
        if not document_uri:
            return create_error_response("Missing required parameter: document_uri")
        
        # Parse S3 URI
        if not document_uri.startswith('s3://'):
            return create_error_response("document_uri must be an S3 URI (s3://bucket/key)")
        
        # Extract bucket and key from S3 URI
        s3_parts = document_uri[5:].split('/', 1)
        if len(s3_parts) != 2:
            return create_error_response("Invalid S3 URI format")
        
        bucket_name, object_key = s3_parts
        
        # Check if document exists
        try:
            s3_client.head_object(Bucket=bucket_name, Key=object_key)
        except Exception as e:
            logger.error(f"Error checking document existence: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if "NoSuchKey" in str(e):
                return create_error_response(f"Document not found: {document_uri}")
            else:
                return create_error_response(f"Error accessing document: {str(e)}")
        
        # Use Textractor to extract text
        try:
            textractor = Textractor(region_name=current_region)
            
            # Use start_document_analysis for multi-page documents (async API)
            document = textractor.start_document_analysis(
                file_source=document_uri,
                features=[TextractFeatures.LAYOUT],
                save_image=False
            )
            
            # Get text based on output format
            if output_format == 'markdown':
                extracted_text = document.to_markdown()
            else:
                extracted_text = document.get_text()
            
            # Get page count
            page_count = len(document.pages)
            
            result = {
                "document_uri": document_uri,
                "extracted_text": extracted_text,
                "output_format": output_format,
                "page_count": page_count,
                "success": True
            }
            
            # Add markdown content for backward compatibility
            if output_format == 'markdown':
                result["markdown_content"] = extracted_text
            
            return create_success_response(result)
            
        except Exception as e:
            logger.error(f"Textract extraction error: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_msg = str(e)
            if "UnsupportedDocumentException" in error_msg:
                return create_error_response("Unsupported document format. Textract supports PDF, PNG, JPEG, and TIFF files.")
            elif "InvalidS3ObjectException" in error_msg:
                return create_error_response("Invalid S3 object. Check that the file exists and is accessible.")
            elif "DocumentTooLargeException" in error_msg:
                return create_error_response("Document too large. Maximum file size is 500 MB.")
            else:
                return create_error_response(f"Textract extraction failed: {error_msg}")
        
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Tool execution failed: {str(e)}")
