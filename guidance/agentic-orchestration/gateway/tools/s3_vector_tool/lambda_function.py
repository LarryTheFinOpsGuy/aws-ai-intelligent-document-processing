import sys
import os
import logging
import traceback
import json
import boto3
import hashlib
from typing import Dict, Any
from embedding_service import EmbeddingService
from document_processor import DocumentProcessor
from response_utils import create_error_response, create_success_response, parse_lambda_event
from auth_utils import log_request

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize services
embedding_service = EmbeddingService()
document_processor = DocumentProcessor()
s3vectors_client = boto3.client('s3vectors')

# Configuration
VECTOR_BUCKET_NAME = os.environ.get('VECTOR_BUCKET_NAME')
INDEX_NAME = os.environ.get('INDEX_NAME', 'documentsimilarity')

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main Lambda handler for S3 vector operations."""
    try:
        logger.info(f"Event: {event}")
        logger.info(f"Context: {context}")

        # Get tool name from context
        tool_name = context.client_context.custom['bedrockAgentCoreToolName']
        logger.info(f"Original toolName: {tool_name}")
        
        # Remove target prefix if present
        delimiter = "___"
        if delimiter in tool_name:
            tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
        logger.info(f"Converted toolName: {tool_name}")
        
        # Use event as parameters
        parameters = event
            
        if tool_name == 'add_document':
            return add_document(parameters)
        elif tool_name == 'search_documents':
            return search_documents(parameters)
        elif tool_name == 'list_documents':
            return list_documents(parameters)
        elif tool_name == 'get_document':
            return get_document(parameters)
        elif tool_name == 'delete_document':
            return delete_document(parameters)
        elif tool_name == 'update_document':
            return update_document(parameters)
        else:
            return create_error_response(f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Tool execution failed: {str(e)}")

def add_document(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Add document with vector embedding."""
    try:
        document_type = parameters.get('document_type')
        sender_name = parameters.get('sender_name')
        sender_address = parameters.get('sender_address')
        processing_workflow = parameters.get('processing_workflow')
        notes = parameters.get('notes', '')
        example_document_uri = parameters.get('example_document_uri')
        instructions_s3_uri = parameters.get('instructions_s3_uri')
        
        if not all([document_type, sender_name, sender_address, processing_workflow, example_document_uri]):
            return create_error_response("Missing required parameters: document_type, sender_name, sender_address, processing_workflow, example_document_uri")
        
        # Generate text description
        text_description = f"{document_type} from {sender_name} {sender_address}"
        
        # Generate document ID based on required fields
        doc_id = f"doc_{hashlib.sha256(f'{document_type}_{sender_name}_{sender_address}_{example_document_uri}'.encode()).hexdigest()[:16]}"
        status = "PENDING REVIEW"
        
        # Process document for embedding
        image_base64 = document_processor.process_document_for_embedding(example_document_uri)
        if not image_base64:
            return create_error_response("Failed to process document for embedding")
        
        # Generate multimodal embedding
        embedding = embedding_service.generate_multimodal_embedding(image_base64, text_description)
        if not embedding:
            return create_error_response("Failed to generate embedding")
        
        # Prepare metadata with filterable and non-filterable fields
        filterable_metadata = {
            "document_type": document_type,
            "sender_name": sender_name,
            "sender_address": sender_address,
            "instructions_s3_uri": instructions_s3_uri,
            "status": status
        }
        
        # Non-filterable metadata (stored but not searchable)
        non_filterable_metadata = {
            "processing_workflow": processing_workflow,
            "text_description": text_description,
            "example_document_uri": example_document_uri,
            "notes": notes
        }
        
        # Combine all metadata for storage
        vector_metadata = {**filterable_metadata, **non_filterable_metadata}
        
        # Store in S3 Vectors
        s3vectors_client.put_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=INDEX_NAME,
            vectors=[{
                "key": doc_id,
                "data": {"float32": embedding},
                "metadata": vector_metadata
            }]
        )
        
        result = {
            "document_id": doc_id,
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error adding document: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error adding document: {str(e)}")

def search_documents(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Search for similar documents using vector similarity."""
    try:
        query_document_uri = parameters.get('query_document_uri')
        query_text = parameters.get('query_text')
        similarity_threshold = parameters.get('similarity_threshold', 0.7)
        max_results = parameters.get('max_results', 10)
        document_type = parameters.get('document_type')
        sender_name = parameters.get('sender_name')
        sender_address = parameters.get('sender_address')
        instructions_s3_uri = parameters.get('instructions_s3_uri')
        status = parameters.get('status')

        # Require either query_text OR all three metadata fields
        if not query_text:
            if not all([document_type, sender_name, sender_address]):
                return create_error_response("Missing required parameters: either query_text OR (document_type, sender_name, sender_address)")
            query_text = f"{document_type} from {sender_name} {sender_address}"
        
        # Process query document
        image_base64 = document_processor.process_document_for_embedding(query_document_uri)
        if not image_base64:
            query_embedding = embedding_service.generate_text_embedding(query_text)
        else:
            query_embedding = embedding_service.generate_multimodal_embedding(image_base64, query_text)
        
        # Generate query embedding
        query_embedding = embedding_service.generate_multimodal_embedding(image_base64, query_text)
        if not query_embedding:
            return create_error_response("Failed to generate query embedding")
        
        # Build metadata filters using proper S3 Vectors filter syntax
        metadata_filters = {}
        filter_conditions = []
        
        if document_type:
            filter_conditions.append({"document_type": {"$eq": document_type}})
        if instructions_s3_uri:
            filter_conditions.append({"instructions_s3_uri": {"$eq": instructions_s3_uri}})
        if status:
            filter_conditions.append({"status": {"$eq": status}})
        
        # Combine multiple conditions with $and if needed
        if len(filter_conditions) > 1:
            metadata_filters = {"$and": filter_conditions}
        elif len(filter_conditions) == 1:
            metadata_filters = filter_conditions[0]
        
        # Search vectors with optional metadata filtering
        query_params = {
            'vectorBucketName': VECTOR_BUCKET_NAME,
            'indexName': INDEX_NAME,
            'queryVector': {"float32": query_embedding},
            'topK': max_results,
            'returnDistance': True,
            'returnMetadata': True
        }
        
        if metadata_filters:
            query_params['filter'] = metadata_filters
        
        response = s3vectors_client.query_vectors(**query_params)
        
        # Filter by similarity threshold and format results
        matches = []
        for result in response.get('vectors', []):
            # S3 Vectors returns distance, convert to similarity (1 - distance)
            distance = result.get('distance', 1.0)
            similarity_score = 1.0 - distance
            
            if similarity_score >= similarity_threshold:
                metadata = result.get('metadata', {})
                
                matches.append({
                    "document_id": result.get('key'),
                    "similarity_score": similarity_score,
                    "document_type": metadata.get('document_type'),
                    "sender_name": metadata.get('sender_name'),
                    "sender_address": metadata.get('sender_address'),
                    "text_description": metadata.get('text_description'),
                    "example_document_uri": metadata.get('example_document_uri'),
                    "processing_workflow": metadata.get('processing_workflow'),
                    "instructions_s3_uri": metadata.get('instructions_s3_uri'),
                    "status": metadata.get('status'),
                    "notes": metadata.get('notes')
                })
        
        result = {
            "matches": matches,
            "total_matches": len(matches),
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error searching documents: {str(e)}")

def get_document(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Get document by ID."""
    try:
        document_id = parameters.get('document_id')
        if not document_id:
            return create_error_response("Missing required parameter: document_id")
        
        # Get vector by key
        response = s3vectors_client.get_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=INDEX_NAME,
            keys=[document_id],
            returnMetadata=True
        )
        
        vectors = response.get('vectors', [])
        if not vectors:
            return create_error_response(f"Document not found: {document_id}")
        
        vector = vectors[0]
        metadata = vector.get('metadata', {})
        
        result = {
            "document_id": document_id,
            "text_description": metadata.get('text_description'),
            "example_document_uri": metadata.get('example_document_uri'),
            "document_type": metadata.get('document_type'),
            "sender_name": metadata.get('sender_name'),
            "sender_address": metadata.get('sender_address'),
            "status": metadata.get('status'),
            "processing_workflow": metadata.get('processing_workflow'),
            "instructions_s3_uri": metadata.get('instructions_s3_uri'),
            "notes": metadata.get('notes')
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error getting document: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error getting document: {str(e)}")

def delete_document(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Delete document by ID."""
    try:
        document_id = parameters.get('document_id')
        if not document_id:
            return create_error_response("Missing required parameter: document_id")
        
        # Delete vector
        s3vectors_client.delete_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=INDEX_NAME,
            keys=[document_id]
        )
        
        result = {
            "document_id": document_id,
            "deleted": True,
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error deleting document: {str(e)}")

def update_document(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Update document metadata fields."""
    try:
        document_id = parameters.get('document_id')
        if not document_id:
            return create_error_response("Missing required parameter: document_id")
        
        # Get allowed update fields
        processing_workflow = parameters.get('processing_workflow')
        notes = parameters.get('notes')
        status = parameters.get('status')
        
        # Validate status if provided
        if status is not None and status not in ("ACTIVE", "PENDING REVIEW", "ARCHIVED"):
            return create_error_response("Status must be one of: ACTIVE, PENDING REVIEW, or ARCHIVED")
        
        # At least one field must be provided
        if not any([processing_workflow is not None, notes is not None, status is not None]):
            return create_error_response("At least one update field required: processing_workflow, notes, or status")
        
        # Get current document
        response = s3vectors_client.get_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=INDEX_NAME,
            keys=[document_id],
            returnMetadata=True,
            returnData=True
        )
        
        vectors = response.get('vectors', [])
        if not vectors:
            return create_error_response(f"Document not found: {document_id}")
        
        vector = vectors[0]
        current_metadata = vector.get('metadata', {})
        current_embedding = vector.get('data', {}).get('float32', [])
        
        # Update only allowed fields
        updated_metadata = current_metadata.copy()
        if processing_workflow is not None:
            updated_metadata['processing_workflow'] = processing_workflow
        if notes is not None:
            updated_metadata['notes'] = notes
        if status is not None:
            updated_metadata['status'] = status
        
        # Store updated vector with same embedding
        s3vectors_client.put_vectors(
            vectorBucketName=VECTOR_BUCKET_NAME,
            indexName=INDEX_NAME,
            vectors=[{
                "key": document_id,
                "data": {"float32": current_embedding},
                "metadata": updated_metadata
            }]
        )
        
        result = {
            "document_id": document_id,
            "updated": True,
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error updating document: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error updating document: {str(e)}")

def list_documents(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """List all documents in the vector index with metadata."""
    try:
        # Get pagination parameters
        max_results = parameters.get('max_results', 100)
        next_token = parameters.get('next_token')
        return_metadata = parameters.get('return_metadata', True)

        logger.info(f"VECTOR_BUCKET_NAME: {VECTOR_BUCKET_NAME}")
        logger.info(f"INDEX_NAME: {INDEX_NAME}")        
        # Prepare list_vectors parameters
        list_params = {
            'vectorBucketName': VECTOR_BUCKET_NAME,
            'indexName': INDEX_NAME,
            'maxResults': min(max_results, 100),  # AWS limit is 100
            'returnMetadata': return_metadata
        }
        
        if next_token:
            list_params['nextToken'] = next_token
        
        # List vectors from S3 Vectors
        response = s3vectors_client.list_vectors(**list_params)
        
        vectors = response.get('vectors', [])
        response_next_token = response.get('nextToken')
        
        # Format results
        documents = []
        for vector in vectors:
            key = vector.get('key', 'Unknown')
            metadata = vector.get('metadata', {})
            
            document_info = {
                "document_id": key,
                "text_description": metadata.get('text_description', ''),
                "example_document_uri": metadata.get('example_document_uri', ''),
                "document_type": metadata.get('document_type', ''),
                "sender_name": metadata.get('sender_name', ''),
                "sender_address": metadata.get('sender_address', ''),
                "status": metadata.get('status', ''),
                "processing_workflow": metadata.get('processing_workflow', ''),
                "instructions_s3_uri": metadata.get('instructions_s3_uri', ''),
                "notes": metadata.get('notes', '')
            }
            
            documents.append(document_info)
        
        result = {
            "documents": documents,
            "total_count": len(documents),
            "has_more": response_next_token is not None,
            "next_token": response_next_token,
            "success": True
        }
        
        return create_success_response(result)
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return create_error_response(f"Error listing documents: {str(e)}")

if __name__ == "__main__":
    # Mock context for testing
    class MockContext:
        class ClientContext:
            custom = {'bedrockAgentCoreToolName': 'document-vector-target___list_documents'}
        client_context = ClientContext()
    
    # Test payload for list_documents
    test_event = {
        "max_results": 10,
        "return_metadata": True
    }
    
    mock_context = MockContext()
    
    print("Testing list_documents tool...")
    try:
        # Call list_documents directly to avoid log_request serialization issue
        result = list_documents(test_event)
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Error: {e}")
