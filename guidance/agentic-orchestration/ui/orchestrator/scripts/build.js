#!/usr/bin/env node

/**
 * Build script for Modern Orchestrator UI
 * Handles environment-specific builds with proper configuration
 */

import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function log(message) {
  console.log(`[BUILD] ${message}`);
}

function error(message) {
  console.error(`[ERROR] ${message}`);
  process.exit(1);
}

function execCommand(command, args, description) {
  log(`${description}...`);
  try {
    const result = execFileSync(command, args, { 
      encoding: 'utf8', 
      stdio: 'inherit',
      cwd: path.join(__dirname, '..')
    });
    return result;
  } catch (err) {
    error(`Failed to ${description.toLowerCase()}: ${err.message}`);
  }
}

function validateEnvironment(environment) {
  const validEnvironments = ['development', 'staging', 'production'];
  if (!validEnvironments.includes(environment)) {
    error(`Invalid environment: ${environment}. Valid options: ${validEnvironments.join(', ')}`);
  }
}

function checkDependencies() {
  const packageJsonPath = path.join(__dirname, '..', 'package.json');
  if (!fs.existsSync(packageJsonPath)) {
    error('package.json not found. Make sure you are in the correct directory.');
  }
  
  const nodeModulesPath = path.join(__dirname, '..', 'node_modules');
  if (!fs.existsSync(nodeModulesPath)) {
    log('node_modules not found. Installing dependencies...');
    execCommand('npm', ['install'], 'Install dependencies');
  }
}

function cleanBuildDirectory() {
  const buildDir = path.join(__dirname, '..', 'build');
  if (fs.existsSync(buildDir)) {
    log('Cleaning previous build...');
    fs.rmSync(buildDir, { recursive: true, force: true });
  }
}

function validateBuild() {
  const buildDir = path.join(__dirname, '..', 'build');
  
  if (!fs.existsSync(buildDir)) {
    error('Build directory was not created');
  }
  
  const indexHtml = path.join(buildDir, 'index.html');
  if (!fs.existsSync(indexHtml)) {
    error('index.html was not generated in build directory');
  }
  
  const buildFiles = fs.readdirSync(buildDir);
  log(`Build completed successfully. Generated ${buildFiles.length} files/directories.`);
  
  // Log build size information
  const stats = fs.statSync(buildDir);
  log(`Build directory: ${buildDir}`);
  
  // Check for common build artifacts
  const assetsDir = path.join(buildDir, 'assets');
  if (fs.existsSync(assetsDir)) {
    const assetFiles = fs.readdirSync(assetsDir);
    log(`Assets directory contains ${assetFiles.length} files`);
  }
}

function main() {
  const environment = process.argv[2] || 'development';
  
  log(`Starting build for ${environment} environment`);
  
  // Validate inputs
  validateEnvironment(environment);
  
  // Check dependencies
  checkDependencies();
  
  // Clean previous build
  cleanBuildDirectory();
  
  // Set NODE_ENV for the build
  process.env.NODE_ENV = environment === 'development' ? 'development' : 'production';
  
  try {
    // Run linting
    log('Running linter...');
    execCommand('npm', ['run', 'lint'], 'Lint code');
    
    // Run build with specific mode
    log(`Building for ${environment} mode...`);
    execCommand('npx', ['vite', 'build', '--mode', environment], `Build application for ${environment}`);
    
    // Validate build output
    validateBuild();
    
    log(`✅ Build completed successfully for ${environment} environment`);
    
  } catch (err) {
    error(`Build failed: ${err.message}`);
  }
}

// Run the build
main();