#!/usr/bin/env node

/**
 * Deployment script for Modern Orchestrator UI using existing UI stack
 * This script deploys to the existing S3 bucket and CloudFront distribution
 * created by the UIHostingStack in infrastructure/stacks/ui/ui_hosting_stack.py
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configuration for different environments
const ENVIRONMENTS = {
  development: {
    coreStackName: 'Core-Dev',
    uiOrchestratorStackName: 'UIOrchestr-Dev',
    uiHostingStackName: 'UI-Dev-hosting'
  },
  staging: {
    coreStackName: 'Core-Staging',
    uiOrchestratorStackName: 'UIOrchestr-Staging',
    uiHostingStackName: 'UI-Staging-hosting'
  },
  production: {
    coreStackName: 'Core-Prod',
    uiOrchestratorStackName: 'UIOrchestr-Prod',
    uiHostingStackName: 'UI-Prod-hosting'
  }
};

function log(message) {
  console.log(`[DEPLOY] ${message}`);
}

function error(message) {
  console.error(`[ERROR] ${message}`);
  process.exit(1);
}

function execCommand(command, args, description) {
  log(`${description}...`);
  try {
    const result = execFileSync(command, args, { encoding: 'utf8', stdio: 'pipe' });
    return result.trim();
  } catch (err) {
    error(`Failed to ${description.toLowerCase()}: ${err.message}`);
  }
}

function getStackOutput(stackName, outputKey, region) {
  try {
    return execCommand('aws', [
      'cloudformation', 'describe-stacks',
      '--stack-name', stackName,
      '--region', region,
      '--query', `Stacks[0].Outputs[?OutputKey=='${outputKey}'].OutputValue`,
      '--output', 'text'
    ], `Get ${outputKey} from ${stackName}`);
  } catch (err) {
    log(`Warning: Could not get ${outputKey} from ${stackName}. Stack may not exist yet.`);
    return null;
  }
}

function createEnvironmentConfig(environment, stackOutputs) {
  // Validate environment to prevent path traversal
  const validEnvironments = ['development', 'staging', 'production'];
  if (!validEnvironments.includes(environment)) {
    throw new Error(`Invalid environment: ${environment}`);
  }
  
  // Safe: environment is validated against allowlist above
  // nosemgrep: path-join-resolve-traversal
  const envFile = path.join(__dirname, '..', `.env.${environment}.local`);
  
  const envContent = `# Auto-generated environment configuration for ${environment}
# Generated on ${new Date().toISOString()}

# AWS Configuration
VITE_AWS_REGION=${stackOutputs.region}
VITE_DOCUMENT_BUCKET=${stackOutputs.documentBucket || 'agenticidp-documents-' + environment}

# Cognito Configuration
VITE_COGNITO_USER_POOL_ID=${stackOutputs.userPoolId || ''}
VITE_COGNITO_USER_POOL_CLIENT_ID=${stackOutputs.userPoolClientId || ''}
VITE_COGNITO_IDENTITY_POOL_ID=${stackOutputs.identityPoolId || ''}

# API Configuration
VITE_API_BASE_URL=${stackOutputs.apiBaseUrl || '/api'}

# Environment-specific settings
VITE_LOG_LEVEL=${environment === 'production' ? 'error' : environment === 'staging' ? 'info' : 'debug'}
VITE_ENABLE_MOCK_API=false
`;

  // nosemgrep: detect-non-literal-fs-filename
  fs.writeFileSync(envFile, envContent);
  log(`Created ${envFile} with deployment configuration`);
  return envFile;
}

function uploadToS3(bucketName, buildDir, region) {
  // First, upload all files except HTML with long cache control
  const assetsCommand = `aws s3 sync ${buildDir} s3://${bucketName} --region ${region} --delete --cache-control "public, max-age=31536000, immutable" --exclude "*.html" --exclude "*.json" --exclude "service-worker.js"`;
  execCommand(assetsCommand, 'Upload static assets to S3');
  
  // Upload HTML files and manifest with short cache control
  const htmlCommand = `aws s3 sync ${buildDir} s3://${bucketName} --region ${region} --cache-control "public, max-age=0, must-revalidate" --include "*.html" --include "*.json" --include "service-worker.js"`;
  execCommand(htmlCommand, 'Upload HTML and manifest files to S3');
  
  log(`Successfully uploaded build to s3://${bucketName}`);
}

function invalidateCloudFront(distributionId, region) {
  const invalidateCommand = `aws cloudfront create-invalidation --distribution-id ${distributionId} --paths "/*"`;
  const result = execCommand(invalidateCommand, 'Create CloudFront invalidation');
  
  try {
    const invalidationData = JSON.parse(result);
    const invalidationId = invalidationData.Invalidation.Id;
    log(`CloudFront invalidation created: ${invalidationId}`);
    return invalidationId;
  } catch (err) {
    log('Warning: Could not parse invalidation response, but invalidation may have been created');
    return null;
  }
}

function waitForInvalidation(distributionId, invalidationId, region, timeout = 600) {
  if (!invalidationId) {
    log('Skipping invalidation wait (no invalidation ID)');
    return;
  }
  
  log('Waiting for CloudFront invalidation to complete (this may take several minutes)...');
  const waitCommand = `timeout ${timeout} aws cloudfront wait invalidation-completed --distribution-id ${distributionId} --id ${invalidationId}`;
  
  try {
    execCommand(waitCommand, 'Wait for CloudFront invalidation');
    log('CloudFront invalidation completed');
  } catch (err) {
    log('Warning: Invalidation wait timed out or failed, but deployment may still be successful');
  }
}

async async function main() {
  const environment = process.argv[2];
  
  if (!environment || !ENVIRONMENTS[environment]) {
    error(`Invalid environment. Use one of: ${Object.keys(ENVIRONMENTS).join(', ')}`);
  }
  
  const config = ENVIRONMENTS[environment];
  const buildDir = path.join(__dirname, '..', 'build');
  
  log(`Starting deployment for ${environment} environment`);
  log(`Build directory: ${buildDir}`);
  
  try {
    // Get stack outputs
    log('Retrieving stack outputs...');
    
    const stackOutputs = {
      region: config.region
    };
    
    // Get Cognito configuration from Core stack
    stackOutputs.userPoolId = getStackOutput(config.coreStackName, 'CognitoUserPoolId', config.region);
    stackOutputs.userPoolClientId = getStackOutput(config.coreStackName, 'CognitoUserPoolClientId', config.region);
    stackOutputs.identityPoolId = getStackOutput(config.coreStackName, 'CognitoIdentityPoolId', config.region);
    
    // Get API Gateway URL from UI Orchestrator stack
    const apiGatewayUrl = getStackOutput(config.uiOrchestratorStackName, 'APIGatewayURL', config.region);
    if (apiGatewayUrl) {
      stackOutputs.apiBaseUrl = apiGatewayUrl.replace(/\/$/, '') + '/api';
    }
    
    // Get S3 bucket and CloudFront distribution from UI Hosting stack
    const webBucketName = getStackOutput(config.uiHostingStackName, 'WebBucketName', config.region);
    const distributionId = getStackOutput(config.uiHostingStackName, 'DistributionId', config.region);
    const websiteUrl = getStackOutput(config.uiHostingStackName, 'WebsiteURL', config.region);
    
    if (!webBucketName) {
      error(`Could not retrieve S3 bucket name from ${config.uiHostingStackName}. Make sure the UI stack is deployed.`);
    }
    
    // Create environment configuration file
    const envFile = createEnvironmentConfig(environment, stackOutputs);
    
    // Rebuild with updated environment
    log('Rebuilding with updated environment configuration...');
    const buildCommand = `npm run build:${environment}`;
    execCommand(buildCommand, 'Rebuild application');
    
    // Check if build directory exists and has content
    if (!fs.existsSync(buildDir)) {
      error(`Build directory not found: ${buildDir}`);
    }
    
    const buildFiles = fs.readdirSync(buildDir);
    if (buildFiles.length === 0) {
      error(`Build directory is empty: ${buildDir}`);
    }
    
    log(`Build directory contains ${buildFiles.length} files/directories`);
    
    // Upload to S3
    log(`Uploading to S3 bucket: ${webBucketName}`);
    uploadToS3(webBucketName, buildDir, config.region);
    
    // Create CloudFront invalidation if distribution exists
    if (distributionId) {
      log(`Invalidating CloudFront distribution: ${distributionId}`);
      const invalidationId = invalidateCloudFront(distributionId, config.region);
      
      // Wait for invalidation to complete (with timeout)
      waitForInvalidation(distributionId, invalidationId, config.region);
    } else {
      log('Warning: No CloudFront distribution ID found, skipping cache invalidation');
    }
    
    log(`✅ Deployment completed successfully for ${environment} environment`);
    
    // Output useful information with prominent display
    console.log('\n' + '='.repeat(80));
    console.log('🚀 DEPLOYMENT SUCCESSFUL');
    console.log('='.repeat(80));
    
    if (websiteUrl) {
      console.log(`\n🌐 APPLICATION URL: ${websiteUrl}`);
    } else if (distributionId) {
      // Construct CloudFront URL if we have distribution ID but no website URL
      console.log(`\n🌐 APPLICATION URL: https://${distributionId}.cloudfront.net`);
    } else {
      console.log(`\n🌐 APPLICATION URL: Check CloudFront distribution in AWS Console`);
    }
    
    console.log(`\n📋 Environment: ${environment}`);
    console.log(`📋 Region: ${config.region}`);
    
    if (distributionId) {
      console.log(`📋 CloudFront Distribution: ${distributionId}`);
    }
    if (webBucketName) {
      console.log(`📋 S3 Bucket: ${webBucketName}`);
    }
    
    console.log('\n💡 You can also get the URL anytime with:');
    console.log(`   aws cloudformation describe-stacks --stack-name ${config.uiHostingStackName} --region ${config.region} --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" --output text`);
    
    console.log('\n' + '='.repeat(80) + '\n');
    
    // Clean up temporary environment file
    if (fs.existsSync(envFile)) {
      fs.unlinkSync(envFile);
      log(`Cleaned up temporary environment file: ${envFile}`);
    }
    
  } catch (err) {
    error(`Deployment failed: ${err.message}`);
  }
}

// Run the deployment
main().catch(err => {
  error(`Unexpected error: ${err.message}`);
});