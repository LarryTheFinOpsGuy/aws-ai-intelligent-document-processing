#!/usr/bin/env node

/**
 * Deployment script for Modern Orchestrator UI
 * Handles S3 upload and CloudFront invalidation for different environments
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
    stackName: 'Core-Dev',
    uiStackName: 'UIOrchestr-Dev',
    modernUIStackName: 'AgenticIDP-ModernUI-Dev'
  },
  staging: {
    stackName: 'Core-Staging',
    uiStackName: 'UIOrchestr-Staging',
    modernUIStackName: 'AgenticIDP-ModernUI-Staging'
  },
  production: {
    stackName: 'Core-Prod',
    uiStackName: 'UIOrchestr-Prod',
    modernUIStackName: 'AgenticIDP-ModernUI-Prod'
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
  return execCommand('aws', [
    'cloudformation', 'describe-stacks',
    '--stack-name', stackName,
    '--region', region,
    '--query', `Stacks[0].Outputs[?OutputKey=='${outputKey}'].OutputValue`,
    '--output', 'text'
  ], `Get ${outputKey} from ${stackName}`);
}

function updateEnvironmentFile(environment, config) {
  // Validate environment to prevent path traversal
  const validEnvironments = ['development', 'staging', 'production'];
  if (!validEnvironments.includes(environment)) {
    throw new Error(`Invalid environment: ${environment}`);
  }
  
  // Safe: environment is validated against allowlist above
  // nosemgrep: path-join-resolve-traversal
  const envFile = path.join(__dirname, '..', `.env.${environment}`);
  // nosemgrep: detect-non-literal-fs-filename
  let envContent = fs.readFileSync(envFile, 'utf8');
  
  // Update environment variables
  Object.entries(config).forEach(([key, value]) => {
    const regex = new RegExp(`^${key}=.*$`, 'm');
    if (envContent.match(regex)) {
      envContent = envContent.replace(regex, `${key}=${value}`);
    } else {
      envContent += `\n${key}=${value}`;
    }
  });
  
  // nosemgrep: detect-non-literal-fs-filename
  fs.writeFileSync(envFile, envContent);
  log(`Updated ${envFile} with deployment configuration`);
}

function uploadToS3(bucketName, buildDir, region) {
  // Sync build directory to S3 bucket
  execCommand('aws', [
    's3', 'sync', buildDir, `s3://${bucketName}`,
    '--region', region,
    '--delete',
    '--cache-control', 'public, max-age=31536000',
    '--exclude', '*.html',
    '--exclude', 'service-worker.js'
  ], 'Upload static assets to S3');
  
  // Upload HTML files with shorter cache control
  execCommand('aws', [
    's3', 'sync', buildDir, `s3://${bucketName}`,
    '--region', region,
    '--cache-control', 'public, max-age=0, must-revalidate',
    '--include', '*.html',
    '--include', 'service-worker.js'
  ], 'Upload HTML files to S3');  execCommand(htmlCommand, 'Upload HTML files to S3');
}

function invalidateCloudFront(distributionId, region) {
  const invalidateCommand = `aws cloudfront create-invalidation --distribution-id ${distributionId} --paths "/*" --region ${region}`;
  const result = execCommand(invalidateCommand, 'Create CloudFront invalidation');
  
  // Extract invalidation ID from result
  const invalidationId = JSON.parse(result).Invalidation.Id;
  log(`CloudFront invalidation created: ${invalidationId}`);
  
  return invalidationId;
}

function waitForInvalidation(distributionId, invalidationId, region) {
  log('Waiting for CloudFront invalidation to complete...');
  const waitCommand = `aws cloudfront wait invalidation-completed --distribution-id ${distributionId} --id ${invalidationId} --region ${region}`;
  execCommand(waitCommand, 'Wait for CloudFront invalidation');
  log('CloudFront invalidation completed');
}

async function main() {
  const environment = process.argv[2];
  
  if (!environment || !ENVIRONMENTS[environment]) {
    error(`Invalid environment. Use one of: ${Object.keys(ENVIRONMENTS).join(', ')}`);
  }
  
  const config = ENVIRONMENTS[environment];
  const buildDir = path.join(__dirname, '..', 'build');
  
  log(`Starting deployment for ${environment} environment`);
  
  // Check if build directory exists
  if (!fs.existsSync(buildDir)) {
    error(`Build directory not found: ${buildDir}. Run 'npm run build:${environment}' first.`);
  }
  
  try {
    // Get stack outputs
    log('Retrieving stack outputs...');
    
    // Get Cognito configuration from Core stack
    const userPoolId = getStackOutput(config.stackName, 'CognitoUserPoolId', config.region);
    const userPoolClientId = getStackOutput(config.stackName, 'CognitoUserPoolClientId', config.region);
    const identityPoolId = getStackOutput(config.stackName, 'CognitoIdentityPoolId', config.region);
    
    // Get API Gateway URL from UI Orchestrator stack
    const apiGatewayUrl = getStackOutput(config.uiStackName, 'APIGatewayURL', config.region);
    
    // Get S3 bucket and CloudFront distribution from ModernUI stack
    const webBucketName = getStackOutput(config.modernUIStackName, 'WebBucketName', config.region);
    const distributionId = getStackOutput(config.modernUIStackName, 'DistributionId', config.region);
    
    // Update environment file with deployment configuration
    const envConfig = {
      VITE_COGNITO_USER_POOL_ID: userPoolId,
      VITE_COGNITO_USER_POOL_CLIENT_ID: userPoolClientId,
      VITE_COGNITO_IDENTITY_POOL_ID: identityPoolId,
      VITE_API_BASE_URL: apiGatewayUrl.replace(/\/$/, '') + '/api'
    };
    
    updateEnvironmentFile(environment, envConfig);
    
    // Rebuild with updated environment
    log('Rebuilding with updated environment configuration...');
    execCommand(`npm run build:${environment}`, 'Rebuild application');
    
    // Upload to S3
    log('Uploading to S3...');
    uploadToS3(webBucketName, buildDir, config.region);
    
    // Create CloudFront invalidation
    log('Invalidating CloudFront cache...');
    const invalidationId = invalidateCloudFront(distributionId, config.region);
    
    // Wait for invalidation to complete
    waitForInvalidation(distributionId, invalidationId, config.region);
    
    log(`Deployment completed successfully for ${environment} environment`);
    log(`Application URL: https://${distributionId}.cloudfront.net`);
    
  } catch (err) {
    error(`Deployment failed: ${err.message}`);
  }
}

// Run the deployment
main().catch(err => {
  error(`Unexpected error: ${err.message}`);
});