"""Shared document processing utilities for all gateway tools."""
import boto3
import base64
import tempfile
import os
from typing import Optional
from pdf2image import convert_from_path
from PIL import Image

class DocumentProcessor:
    def __init__(self):
        self.s3_client = boto3.client("s3")
    
    def download_from_s3(self, s3_uri: str) -> bytes:
        """Download document from S3 URI."""
        # Parse s3://bucket/key format
        parts = s3_uri.replace("s3://", "").split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        bucket, key = parts[0], parts[1]
        
        response = self.s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    
    def resize_image_if_needed(self, image, max_pixels=4_000_000):
        """Resize image if it exceeds pixel limits."""
        width, height = image.size
        total_pixels = width * height
        
        if total_pixels > max_pixels:
            resize_factor = (max_pixels / total_pixels) ** 0.5
            new_width = int(width * resize_factor)
            new_height = int(height * resize_factor)
            return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        return image
    
    def pdf_first_page_to_base64(self, pdf_bytes: bytes) -> Optional[str]:
        """Convert first page of PDF to base64 PNG."""
        try:
            # Create temporary file for PDF processing
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(pdf_bytes)
                temp_pdf.flush()
                temp_pdf_path = temp_pdf.name
            
            try:
                # Convert first page to image
                images = convert_from_path(temp_pdf_path, first_page=1, last_page=1, dpi=200)
                
                if not images:
                    return None
                
                # Resize image if needed
                resized_image = self.resize_image_if_needed(images[0])
                
                # Convert to PNG bytes
                import io
                img_byte_arr = io.BytesIO()
                resized_image.save(img_byte_arr, format="PNG", optimize=True, quality=85)
                img_byte_arr.seek(0)
                
                # Convert to base64
                return base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
                    
        except Exception as e:
            print(f"Error converting PDF to image: {e}")
            return None
    
    def process_document_for_embedding(self, s3_uri: str) -> Optional[str]:
        """Download document and convert first page to base64 image."""
        try:
            pdf_bytes = self.download_from_s3(s3_uri)
            return self.pdf_first_page_to_base64(pdf_bytes)
        except Exception as e:
            print(f"Error processing document: {e}")
            return None
