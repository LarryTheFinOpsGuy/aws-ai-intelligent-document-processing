// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

export async function uploadToS3WithPresignedUrl(
  file: File,
  apiClient: any
): Promise<string> {
  console.log('🔍 S3 Upload - Starting presigned URL upload');
  console.log('📁 File:', file.name, 'Size:', file.size, 'Type:', file.type);
  
  // Get presigned POST URL from API
  console.log('📤 Requesting presigned POST URL...');
  const response = await apiClient.makeRequest('post', '/upload', {
    fileName: file.name,
    contentType: file.type
  });
  
  console.log('✅ Received presigned POST data');
  const { presignedPost, s3Uri } = response;
  
  // Upload to S3 using presigned POST
  const formData = new FormData();
  Object.entries(presignedPost.fields).forEach(([key, value]) => {
    formData.append(key, value as string);
  });
  formData.append('file', file);
  
  console.log('📤 Uploading to S3...');
  const uploadResponse = await fetch(presignedPost.url, {
    method: 'POST',
    body: formData,
  });
  
  if (!uploadResponse.ok) {
    throw new Error(`Upload failed: ${uploadResponse.status}`);
  }
  
  console.log('✅ Upload successful!');
  console.log('🎉 S3 URI:', s3Uri);
  return s3Uri;
}
