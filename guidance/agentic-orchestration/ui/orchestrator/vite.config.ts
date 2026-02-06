// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';
import { resolve } from 'path';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isDevelopment = mode === 'development';
  const isProduction = mode === 'production';
  
  return {
  plugins: [
    react({
      // Use automatic JSX runtime (React 17+)
      jsxRuntime: 'automatic',
      // Include all TypeScript and JavaScript files for JSX transformation
      include: '**/*.{js,jsx,ts,tsx}',
    }),
   
    // Enable SVG import as React components
    svgr(),
  ],

  // Ensure all .js, .jsx, .ts, and .tsx files are treated as JSX
  esbuild: {
    jsx: 'automatic',
  },

  // Development server configuration
  server: {
    port: 3000,
    open: true,
    // Enable CORS for AWS Amplify
    cors: true,
    // Proxy API requests to bypass CORS in development
    proxy: {
      '/api': {
        target: 'https://2dbzvy4m6l.execute-api.us-west-2.amazonaws.com/prod',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Sending Request to the Target:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
          });
        },
      },
    },
  },

  // Build configuration
  build: {
    outDir: 'build',
    sourcemap: isDevelopment ? 'inline' : false,
    // Increase chunk size warning limit
    chunkSizeWarningLimit: 1000,
    // Minification for production
    minify: isProduction ? 'esbuild' : false,
    // Target modern browsers in production
    target: isProduction ? 'es2020' : 'esnext',
    rollupOptions: {
      output: {
        // Manual chunking for better code splitting
        manualChunks: {
          'aws-amplify': ['aws-amplify', '@aws-amplify/ui-react'],
          'aws-sdk': [
            '@aws-sdk/client-s3',
            '@aws-sdk/client-ssm',
            '@aws-sdk/client-cognito-identity',
            '@aws-sdk/s3-request-presigner',
          ],
          'cloudscape': ['@cloudscape-design/components', '@cloudscape-design/global-styles'],
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
        },
        // Asset naming for production
        ...(isProduction && {
          entryFileNames: 'assets/[name].[hash].js',
          chunkFileNames: 'assets/[name].[hash].js',
          assetFileNames: 'assets/[name].[hash].[ext]'
        })
      },
    },
  },

  // Resolve configuration
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
    // Ensure proper module resolution
    extensions: ['.mjs', '.js', '.jsx', '.ts', '.tsx', '.json'],
  },

  // Define global constants
  define: {
    // Ensure process.env is available for compatibility
    'process.env': {},
    // Define build-time constants
    __DEV__: isDevelopment,
    __PROD__: isProduction,
  },

  // Optimize dependencies
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      'aws-amplify',
      '@aws-amplify/ui-react',
      '@cloudscape-design/components',
      '@cloudscape-design/global-styles',
    ],
    exclude: ['@aws-sdk/signature-v4-multi-region'],
    esbuildOptions: {
      loader: {
        '.js': 'jsx',
        '.ts': 'tsx',
      },
      // Suppress source map warnings for dependencies
      sourcemap: false,
    },
  },

  // Test configuration for Vitest
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.js'],
  },

  // Suppress source map warnings in development
  ...(mode === 'development' && {
    logLevel: 'info',
    clearScreen: false,
  }),

  // CSS configuration
  css: {
    modules: {
      localsConvention: 'camelCase',
    },
    // PostCSS configuration for production optimization
    postcss: isProduction ? {
      plugins: [
        // Add autoprefixer and other PostCSS plugins if needed
      ]
    } : undefined,
  },
  };
});