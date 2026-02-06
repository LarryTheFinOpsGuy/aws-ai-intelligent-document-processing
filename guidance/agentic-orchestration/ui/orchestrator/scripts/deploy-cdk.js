#!/usr/bin/env node

/**
 * CDK-integrated deployment script for Modern Orchestrator UI
 * This script integrates with the CDK deployment process and can be called
 * from CDK custom resources or as a standalone deployment tool
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Default configuration - region will be determined from AWS CLI config
const DEFAULT_CONFIG = {
  appName: 'agenticidp'
};

function log(message) {
  console.log(`[CDK-DEPLOY] ${message}`);
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

function getAWSRegion() {
  // Get region from AWS CLI default configuration
  try {
    const result = execCommand('aws', ['configure', 'get', 'region'], 'Get AWS region', { silent: true, allowFailure: true });
    if (result && result.trim()) {
      return result.trim();
    }
  } catch (err) {
    log('Warning: Could not get region from AWS CLI, will use environment variable or AWS SDK default');
  }
  return process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION || null;
}

function getCDKOutput(stackName, outputKey) {
  // Use AWS CLI directly to get stack outputs (uses default region from AWS config)
  const result = execCommand('aws', [
    'cloudformation', 'describe-stacks',
    '--stack-name', stackName,
    '--query', `Stacks[0].Outputs[?OutputKey=='${outputKey}'].OutputValue`,
    '--output', 'text'
  ], `Get ${outputKey} from ${stackName}`, { silent: true, allowFailure: true });
  
  if (!result || result === 'NotFound' || result.includes('does not exist')) {
    log(`Warning: Could not get ${outputKey} from stack ${stackName}`);
    return null;
  }
  
  return result;
}

function createDeploymentConfig(environment, config) {
  // Map environment names to match CDK stack naming convention
  const envMapping = {
    'development': 'Dev',
    'staging': 'Staging', 
    'production': 'Prod'
  };
  
  const envSuffix = envMapping[environment] || environment.charAt(0).toUpperCase() + environment.slice(1);
  
  const deploymentConfig = {
    environment,
    appName: config.appName || DEFAULT_CONFIG.appName,
    stacks: {
      core: `AgenticIDP-Core-${envSuffix}`,
      uiOrchestrator: `AgenticIDP-UIOrchestr-${envSuffix}`,
      modernUI: `AgenticIDP-ModernUI-${envSuffix}`
    }
  };
  
  return deploymentConfig;
}

function buildApplication(environment, config) {
  log(`Building application for ${environment} environment`);
  
  // Clean previous build
  const buildDir = path.join(__dirname, '..', 'build');
  if (fs.existsSync(buildDir)) {
    fs.rmSync(buildDir, { recursive: true, force: true });
  }
  
  // Validate environment to prevent path traversal
  const validEnvironments = ['development', 'staging', 'production'];
  if (!validEnvironments.includes(environment)) {
    throw new Error(`Invalid environment: ${environment}`);
  }
  
  // Create temporary environment file with known values
  // Safe: environment is validated against allowlist above
  // nosemgrep: path-join-resolve-traversal
  const tempEnvFile = path.join(__dirname, '..', `.env.${environment}.local`);
  const envContent = `# Temporary build configuration
VITE_AWS_REGION=${config.region}
VITE_LOG_LEVEL=${environment === 'production' ? 'error' : 'debug'}
VITE_ENABLE_MOCK_API=false
`;
  
  // nosemgrep: detect-non-literal-fs-filename
  fs.writeFileSync(tempEnvFile, envContent);
  
  try {
    // Run build
    execCommand('node', ['scripts/build.js', environment], `Build application for ${environment}`);
    
    // Validate build
    // nosemgrep: detect-non-literal-fs-filename
    if (!fs.existsSync(buildDir) || fs.readdirSync(buildDir).length === 0) {
      error('Build failed - no output generated');
    }
    
    log('Build completed successfully');
    
  } finally {

    // Clean up temporary file
    // nosemgrep: detect-non-literal-fs-filename
    if (fs.existsSync(tempEnvFile)) {
      // nosemgrep: detect-non-literal-fs-filename
      fs.unlinkSync(tempEnvFile);
    }
  }
}

function deployToS3(bucketName) {
  const buildDir = path.join(__dirname, '..', 'build');
  
  if (!bucketName) {
    error('S3 bucket name is required for deployment');
  }
  
  log(`Deploying to S3 bucket: ${bucketName}`);
  
  // Upload static assets with long cache
  execCommand('aws', [
    's3', 'sync', buildDir, `s3://${bucketName}`,
    '--delete',
    '--cache-control', 'public, max-age=31536000, immutable',
    '--exclude', '*.html',
    '--exclude', '*.json',
    '--exclude', 'service-worker.js'
  ], 'Upload static assets');
  
  // Upload HTML and manifest files with short cache
  execCommand('aws', [
    's3', 'sync', buildDir, `s3://${bucketName}`,
    '--cache-control', 'public, max-age=0, must-revalidate',
    '--include', '*.html',
    '--include', '*.json',
    '--include', 'service-worker.js'
  ], 'Upload HTML and manifest files');
  
  log('S3 deployment completed');
}

function invalidateCloudFront(distributionId) {
  if (!distributionId) {
    log('No CloudFront distribution ID provided, skipping invalidation');
    return;
  }
  
  log(`Invalidating CloudFront distribution: ${distributionId}`);
  
  const result = execCommand('aws', [
    'cloudfront', 'create-invalidation',
    '--distribution-id', distributionId,
    '--paths', '/*'
  ], 'Create CloudFront invalidation', { silent: true });
  
  try {
    const invalidationData = JSON.parse(result);
    const invalidationId = invalidationData.Invalidation.Id;
    log(`Invalidation created: ${invalidationId}`);
    
    // Don't wait for invalidation in automated deployments to avoid timeouts
    log('Invalidation is processing in the background');
    
  } catch (err) {
    log('Warning: Could not parse invalidation response');
  }
}

function updateEnvironmentConfig(environment, deploymentConfig, stackOutputs) {
  // Validate environment to prevent path traversal
  const validEnvironments = ['development', 'staging', 'production'];
  if (!validEnvironments.includes(environment)) {
    throw new Error(`Invalid environment: ${environment}`);
  }
  
  // Safe: environment is validated against allowlist above
  // nosemgrep: path-join-resolve-traversal
  const envFile = path.join(__dirname, '..', `.env.${environment}`);
  
  // nosemgrep: detect-non-literal-fs-filename
  if (!fs.existsSync(envFile)) {
    log(`Creating new environment file: ${envFile}`);
  }
  
  // nosemgrep: detect-non-literal-fs-filename
  let envContent = fs.existsSync(envFile) ? fs.readFileSync(envFile, 'utf8') : '';
  
  // Get AWS region from CLI configuration
  const awsRegion = getAWSRegion();
  
  // Update or add configuration values
  const updates = {
    VITE_AWS_REGION: awsRegion,
    VITE_COGNITO_USER_POOL_ID: stackOutputs.userPoolId || '',
    VITE_COGNITO_USER_POOL_CLIENT_ID: stackOutputs.userPoolClientId || '',
    VITE_COGNITO_IDENTITY_POOL_ID: stackOutputs.identityPoolId || '',
    VITE_API_BASE_URL: stackOutputs.apiBaseUrl || '/api'
  };
  
  Object.entries(updates).forEach(([key, value]) => {
    const regex = new RegExp(`^${key}=.*$`, 'm');
    if (envContent.match(regex)) {
      envContent = envContent.replace(regex, `${key}=${value}`);
    } else {
      envContent += `\n${key}=${value}`;
    }
  });
  
  // nosemgrep: detect-non-literal-fs-filename
  fs.writeFileSync(envFile, envContent);
  log(`Updated environment configuration: ${envFile}`);
}

function main() {
  const args = process.argv.slice(2);
  const environment = args[0] || 'development';
  
  // Parse additional configuration from command line or environment
  const config = {
    region: process.env.AWS_REGION || process.env.CDK_DEFAULT_REGION || DEFAULT_CONFIG.region,
    appName: process.env.APP_NAME || DEFAULT_CONFIG.appName,
    bucketName: process.env.S3_BUCKET_NAME,
    distributionId: process.env.CLOUDFRONT_DISTRIBUTION_ID,
    skipBuild: process.env.SKIP_BUILD === 'true',
    skipDeploy: process.env.SKIP_DEPLOY === 'true'
  };
  
  log(`Starting CDK deployment for ${environment} environment`);
  log(`Configuration: ${JSON.stringify(config, null, 2)}`);
  
  const deploymentConfig = createDeploymentConfig(environment, config);
  
  try {
    // Get stack outputs FIRST
    log('Retrieving stack outputs...');
    const stackOutputs = {};
    
    // Try to get outputs from CDK stacks - use actual output key names
    stackOutputs.userPoolId = getCDKOutput(deploymentConfig.stacks.core, 'CognitoAuthUserPoolIdC6D8C16B', deploymentConfig.region);
    stackOutputs.userPoolClientId = getCDKOutput(deploymentConfig.stacks.core, 'CognitoAuthWebAppClientId154D07DE', deploymentConfig.region);
    stackOutputs.identityPoolId = getCDKOutput(deploymentConfig.stacks.core, 'CognitoAuthIdentityPoolId976BC1CF', deploymentConfig.region);
    
    const apiGatewayUrl = getCDKOutput(deploymentConfig.stacks.uiOrchestrator, 'APIGatewayURL', deploymentConfig.region);
    if (apiGatewayUrl) {
      stackOutputs.apiBaseUrl = apiGatewayUrl.replace(/\/$/, '') + '/api';
    }
    
    // Update environment configuration BEFORE building
    updateEnvironmentConfig(environment, deploymentConfig, stackOutputs);
    
    // Build application if not skipped
    if (!config.skipBuild) {
      buildApplication(environment, deploymentConfig);
    } else {
      log('Skipping build (SKIP_BUILD=true)');
    }
    
    // Skip deployment if requested (useful for build-only scenarios)
    if (config.skipDeploy) {
      log('Skipping deployment (SKIP_DEPLOY=true)');
      return;
    }
    
    // Get S3 bucket and CloudFront distribution from Modern UI stack
    const bucketName = config.bucketName || getCDKOutput(deploymentConfig.stacks.modernUI, 'WebBucketName');
    const distributionId = config.distributionId || getCDKOutput(deploymentConfig.stacks.modernUI, 'DistributionId');
    
    // Deploy to S3 if bucket is available
    if (bucketName) {
      deployToS3(bucketName);
      
      // Invalidate CloudFront if distribution is available
      if (distributionId) {
        invalidateCloudFront(distributionId);
      }
    } else {
      log('Warning: No S3 bucket found for deployment. Make sure UI hosting stack is deployed.');
    }
    
    log(`✅ CDK deployment completed for ${environment} environment`);
    
    // Output useful information with prominent display
    console.log('\n' + '='.repeat(80));
    console.log('🚀 DEPLOYMENT SUCCESSFUL');
    console.log('='.repeat(80));
    
    const websiteUrl = getCDKOutput(deploymentConfig.stacks.modernUI, 'WebsiteURL', deploymentConfig.region);
    if (websiteUrl) {
      console.log(`\n🌐 APPLICATION URL: ${websiteUrl}`);
      console.log(`\n📋 Environment: ${environment}`);
      console.log(`📋 Region: ${deploymentConfig.region}`);
      
      if (distributionId) {
        console.log(`📋 CloudFront Distribution: ${distributionId}`);
      }
      if (bucketName) {
        console.log(`📋 S3 Bucket: ${bucketName}`);
      }
      
      console.log('\n💡 You can also get the URL anytime with:');
      console.log(`   aws cloudformation describe-stacks --stack-name ${deploymentConfig.stacks.modernUI} --region ${deploymentConfig.region} --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" --output text`);
      
    } else {
      console.log('\n⚠️  Could not retrieve application URL from CDK stack.');
      console.log('   This might mean the Modern Orchestrator UI hosting stack is not deployed yet.');
      console.log('\n💡 To deploy the hosting stack, run:');
      console.log(`   cdk deploy ${deploymentConfig.stacks.modernUI}`);
      console.log('\n💡 To get the URL manually after deployment, run:');
      console.log(`   aws cloudformation describe-stacks --stack-name ${deploymentConfig.stacks.modernUI} --region ${deploymentConfig.region} --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" --output text`);
    }
    
    console.log('\n' + '='.repeat(80) + '\n');
    
  } catch (err) {
    error(`CDK deployment failed: ${err.message}`);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { main, createDeploymentConfig, buildApplication, deployToS3, invalidateCloudFront };