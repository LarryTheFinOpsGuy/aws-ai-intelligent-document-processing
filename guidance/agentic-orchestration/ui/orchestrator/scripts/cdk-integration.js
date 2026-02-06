#!/usr/bin/env node

/**
 * CDK Integration Script for Modern Orchestrator UI
 * This script is designed to be called from CDK custom resources
 * to handle the build and deployment of the React application
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function log(message) {
  console.log(`[CDK-INTEGRATION] ${message}`);
}

function error(message) {
  console.error(`[ERROR] ${message}`);
  process.exit(1);
}

function execCommand(command, args, description, options = {}) {
  log(`${description}...`);
  try {
    const result = execFileSync(command, args, { 
      encoding: 'utf8', 
      stdio: options.silent ? 'pipe' : 'inherit',
      cwd: options.cwd || path.join(__dirname, '..'),
      ...options
    });
    return result ? result.trim() : '';
  } catch (err) {
    if (options.allowFailure) {
      log(`Warning: ${description} failed: ${err.message}`);
      return null;
    }
    error(`Failed to ${description.toLowerCase()}: ${err.message}`);
  }
}

/**
 * Main integration function that can be called from CDK
 * @param {Object} event - CDK custom resource event
 * @param {Object} context - Lambda context (if running in Lambda)
 */
async function handleCDKEvent(event, context) {
  const requestType = event?.RequestType || 'Create';
  const resourceProperties = event?.ResourceProperties || {};
  
  log(`Handling CDK event: ${requestType}`);
  log(`Resource properties: ${JSON.stringify(resourceProperties, null, 2)}`);
  
  try {
    switch (requestType) {
      case 'Create':
      case 'Update':
        await deployApplication(resourceProperties);
        break;
      case 'Delete':
        await cleanupApplication(resourceProperties);
        break;
      default:
        log(`Unknown request type: ${requestType}`);
    }
    
    return {
      Status: 'SUCCESS',
      PhysicalResourceId: resourceProperties.PhysicalResourceId || 'modern-orchestrator-ui',
      Data: {
        Message: `Successfully handled ${requestType} request`
      }
    };
    
  } catch (err) {
    error(`CDK event handling failed: ${err.message}`);
    return {
      Status: 'FAILED',
      PhysicalResourceId: resourceProperties.PhysicalResourceId || 'modern-orchestrator-ui',
      Reason: err.message
    };
  }
}

async function deployApplication(properties) {
  const {
    Environment = 'development',
    S3BucketName,
    CloudFrontDistributionId,
    ApiGatewayUrl,
    CognitoUserPoolId,
    CognitoUserPoolClientId,
    CognitoIdentityPoolId,
    AwsRegion
  } = properties;
  
  log(`Deploying application for ${Environment} environment`);
  
  // Create environment configuration
  const envConfig = {
    VITE_AWS_REGION: AwsRegion,
    VITE_COGNITO_USER_POOL_ID: CognitoUserPoolId || '',
    VITE_COGNITO_USER_POOL_CLIENT_ID: CognitoUserPoolClientId || '',
    VITE_COGNITO_IDENTITY_POOL_ID: CognitoIdentityPoolId || '',
    VITE_API_BASE_URL: ApiGatewayUrl ? `${ApiGatewayUrl.replace(/\/$/, '')}/api` : '/api',
    VITE_LOG_LEVEL: Environment === 'production' ? 'error' : 'debug',
    VITE_ENABLE_MOCK_API: 'false'
  };
  
  // Create temporary environment file
  const tempEnvFile = path.join(__dirname, '..', `.env.${Environment}.local`);
  const envContent = Object.entries(envConfig)
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');
  
  fs.writeFileSync(tempEnvFile, envContent);
  log(`Created temporary environment file: ${tempEnvFile}`);
  
  try {
    // Install dependencies if needed
    const nodeModulesPath = path.join(__dirname, '..', 'node_modules');
    if (!fs.existsSync(nodeModulesPath)) {
      execCommand('npm', ['ci'], 'Install dependencies');
    }
    
    // Build application
    execCommand('npm', ['run', `build:${Environment}`], `Build application for ${Environment}`);
    
    // Deploy to S3 if bucket is provided
    if (S3BucketName) {
      await deployToS3(S3BucketName, AwsRegion);
      
      // Invalidate CloudFront if distribution is provided
      if (CloudFrontDistributionId) {
        await invalidateCloudFront(CloudFrontDistributionId, AwsRegion);
      }
    } else {
      log('Warning: No S3 bucket provided, skipping deployment');
    }
    
  } finally {
    // Clean up temporary file
    if (fs.existsSync(tempEnvFile)) {
      fs.unlinkSync(tempEnvFile);
      log(`Cleaned up temporary environment file: ${tempEnvFile}`);
    }
  }
}

async function deployToS3(bucketName, region) {
  const buildDir = path.join(__dirname, '..', 'build');
  
  if (!fs.existsSync(buildDir)) {
    error('Build directory not found. Build must be completed before deployment.');
  }
  
  log(`Deploying to S3 bucket: ${bucketName}`);
  
  // Upload static assets with long cache
  execCommand('aws', [
    's3', 'sync', buildDir, `s3://${bucketName}`,
    '--region', region,
    '--delete',
    '--cache-control', 'public, max-age=31536000, immutable',
    '--exclude', '*.html',
    '--exclude', '*.json',
    '--exclude', 'service-worker.js'
  ], 'Upload static assets to S3');
  
  // Upload HTML and manifest files with short cache
  execCommand('aws', [
    's3', 'sync', buildDir, `s3://${bucketName}`,
    '--region', region,
    '--cache-control', 'public, max-age=0, must-revalidate',
    '--include', '*.html',
    '--include', '*.json',
    '--include', 'service-worker.js'
  ], 'Upload HTML and manifest files to S3');
  
  log('S3 deployment completed successfully');
}

async function invalidateCloudFront(distributionId, region) {
  log(`Invalidating CloudFront distribution: ${distributionId}`);
  
  const result = execCommand('aws', [
    'cloudfront', 'create-invalidation',
    '--distribution-id', distributionId,
    '--paths', '/*'
  ], 'Create CloudFront invalidation', { silent: true });
  
  try {
    const invalidationData = JSON.parse(result);
    const invalidationId = invalidationData.Invalidation.Id;
    log(`CloudFront invalidation created: ${invalidationId}`);
    
    // Don't wait for invalidation in CDK context to avoid timeouts
    log('Invalidation is processing in the background');
    
  } catch (err) {
    log('Warning: Could not parse invalidation response, but invalidation may have been created');
  }
}

async function cleanupApplication(properties) {
  const { S3BucketName, AwsRegion } = properties;
  
  log('Cleaning up application resources');
  
  if (S3BucketName) {
    log(`Cleaning up S3 bucket: ${S3BucketName}`);
    
    // Remove all objects from the bucket (but don't delete the bucket itself)
    execCommand('aws', [
      's3', 'rm', `s3://${S3BucketName}`,
      '--recursive',
      '--region', AwsRegion
    ], 'Clean up S3 bucket contents', { allowFailure: true });
  }
  
  // Clean up local build artifacts
  const buildDir = path.join(__dirname, '..', 'build');
  if (fs.existsSync(buildDir)) {
    fs.rmSync(buildDir, { recursive: true, force: true });
    log('Cleaned up local build directory');
  }
  
  log('Cleanup completed');
}

// Command line interface
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  
  if (!command) {
    error('Usage: node cdk-integration.js <command> [options]');
  }
  
  switch (command) {
    case 'deploy':
      const environment = args[1] || 'development';
      const properties = {
        Environment: environment,
        S3BucketName: process.env.S3_BUCKET_NAME,
        CloudFrontDistributionId: process.env.CLOUDFRONT_DISTRIBUTION_ID,
        ApiGatewayUrl: process.env.API_GATEWAY_URL,
        CognitoUserPoolId: process.env.COGNITO_USER_POOL_ID,
        CognitoUserPoolClientId: process.env.COGNITO_USER_POOL_CLIENT_ID,
        CognitoIdentityPoolId: process.env.COGNITO_IDENTITY_POOL_ID,
        AwsRegion: process.env.AWS_REGION
      };
      
      await deployApplication(properties);
      break;
      
    case 'cleanup':
      const cleanupProperties = {
        S3BucketName: process.env.S3_BUCKET_NAME,
        AwsRegion: process.env.AWS_REGION
      };
      
      await cleanupApplication(cleanupProperties);
      break;
      
    case 'handle-event':
      // Handle CDK custom resource event from stdin
      const eventData = JSON.parse(fs.readFileSync(0, 'utf8'));
      const result = await handleCDKEvent(eventData);
      console.log(JSON.stringify(result, null, 2));
      break;
      
    default:
      error(`Unknown command: ${command}`);
  }
}

// Export for use as a module
export { handleCDKEvent, deployApplication, cleanupApplication };

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(err => {
    error(`Script failed: ${err.message}`);
  });
}