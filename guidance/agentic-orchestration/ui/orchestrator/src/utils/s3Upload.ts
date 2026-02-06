// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { fetchAuthSession } from 'aws-amplify/auth';

const REGION = import.meta.env.VITE_AWS_REGION || 'us-west-2';

export async function uploadToS3(
  file: File,
  bucketName: string,
  onProgress?: (progress: number) => void
): Promise<string> {
  console.log('🔍 S3 Upload - Starting upload process');
  console.log('📁 File:', file.name, 'Size:', file.size, 'Type:', file.type);
  console.log('🪣 Bucket:', bucketName);
  
  const session = await fetchAuthSession();
  console.log('🔐 Auth session fetched:', {
    hasCredentials: !!session.credentials,
    hasIdentityId: !!session.identityId,
    credentials: session.credentials ? {
      accessKeyId: session.credentials.accessKeyId?.substring(0, 10) + '...',
      hasSecretKey: !!session.credentials.secretAccessKey,
      hasSessionToken: !!session.credentials.sessionToken
    } : null
  });
  
  const credentials = session.credentials;

  if (!credentials) {
    console.error('❌ No credentials available from auth session');
    throw new Error('No credentials available');
  }

  const s3Client = new S3Client({
    region: REGION,
    credentials,
  });
  console.log('✅ S3 Client created for region:', REGION);

  const key = `uploads/${Date.now()}-${file.name}`;
  console.log('🔑 Upload key:', key);
  
  const command = new PutObjectCommand({
    Bucket: bucketName,
    Key: key,
    Body: file,
    ContentType: file.type,
  });

  console.log('📤 Sending PutObject command...');
  await s3Client.send(command);
  console.log('✅ Upload successful!');
  
  if (onProgress) {
    onProgress(100);
  }

  const s3Uri = `s3://${bucketName}/${key}`;
  console.log('🎉 Final S3 URI:', s3Uri);
  return s3Uri;
}
