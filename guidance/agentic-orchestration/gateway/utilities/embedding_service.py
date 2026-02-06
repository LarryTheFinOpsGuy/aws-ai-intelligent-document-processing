"""Shared Bedrock embedding service for all gateway tools."""
import boto3
import json
from typing import List, Optional

class EmbeddingService:
    def __init__(self):
        self.bedrock_client = boto3.client("bedrock-runtime")
        self.model_id = "amazon.titan-embed-image-v1"
    
    def generate_multimodal_embedding(self, image_base64: str, text_description: str) -> Optional[List[float]]:
        """Generate multimodal embedding using Bedrock Titan."""
        try:
            request_body = {
                "inputImage": image_base64,
                "inputText": text_description,
                "embeddingConfig": {"outputEmbeddingLength": 1024}
            }
            
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('embedding')
            
        except Exception as e:
            print(f"Error generating embedding: {str(e)}")
            return None
    
    def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """Generate text-only embedding using Titan Text."""
        try:
            request_body = {
                "inputText": text,
                "dimensions": 1024
            }
            
            response = self.bedrock_client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps(request_body),
                contentType="application/json"
            )
            
            response_body = json.loads(response['body'].read())
            return response_body.get('embedding')
            
        except Exception as e:
            print(f"Error generating text embedding: {str(e)}")
            return None
