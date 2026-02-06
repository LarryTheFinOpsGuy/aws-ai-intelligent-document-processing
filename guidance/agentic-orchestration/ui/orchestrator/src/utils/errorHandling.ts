// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

/**
 * Comprehensive error handling utilities for the Modern Orchestrator UI
 * Provides user-friendly error messages, network connectivity handling,
 * and standardized error processing across the application.
 */

export interface ErrorDetails {
  type: 'network' | 'authentication' | 'authorization' | 'validation' | 'server' | 'timeout' | 'unknown';
  title: string;
  message: string;
  userAction?: string;
  technicalDetails?: string;
  retryable: boolean;
}

/**
 * Categorizes and transforms errors into user-friendly messages
 */
export const processError = (error: any): ErrorDetails => {
  // Handle network connectivity errors
  if (!navigator.onLine) {
    return {
      type: 'network',
      title: 'No Internet Connection',
      message: 'Please check your internet connection and try again.',
      userAction: 'Check your network connection and retry the operation.',
      retryable: true,
    };
  }

  // Handle Axios errors
  if (error.response) {
    const status = error.response.status;
    const data = error.response.data;

    switch (status) {
      case 400:
        return {
          type: 'validation',
          title: 'Invalid Request',
          message: data?.message || 'The request contains invalid data. Please check your input and try again.',
          userAction: 'Review your input and correct any errors.',
          technicalDetails: `HTTP 400: ${data?.error || 'Bad Request'}`,
          retryable: false,
        };

      case 401:
        return {
          type: 'authentication',
          title: 'Authentication Required',
          message: 'Your session has expired. Please sign in again to continue.',
          userAction: 'Sign out and sign back in to refresh your session.',
          technicalDetails: `HTTP 401: ${data?.error || 'Unauthorized'}`,
          retryable: false,
        };

      case 403:
        return {
          type: 'authorization',
          title: 'Access Denied',
          message: 'You do not have permission to perform this action.',
          userAction: 'Contact your administrator if you believe you should have access.',
          technicalDetails: `HTTP 403: ${data?.error || 'Forbidden'}`,
          retryable: false,
        };

      case 404:
        return {
          type: 'server',
          title: 'Resource Not Found',
          message: 'The requested resource could not be found.',
          userAction: 'Please verify the resource exists and try again.',
          technicalDetails: `HTTP 404: ${data?.error || 'Not Found'}`,
          retryable: false,
        };

      case 429:
        return {
          type: 'server',
          title: 'Too Many Requests',
          message: 'You have made too many requests. Please wait a moment and try again.',
          userAction: 'Wait a few minutes before retrying.',
          technicalDetails: `HTTP 429: Rate limit exceeded`,
          retryable: true,
        };

      case 500:
      case 502:
      case 503:
      case 504:
        return {
          type: 'server',
          title: 'Server Error',
          message: 'The server encountered an error. Please try again in a few moments.',
          userAction: 'Wait a moment and retry. If the problem persists, contact support.',
          technicalDetails: `HTTP ${status}: ${data?.error || 'Internal Server Error'}`,
          retryable: true,
        };

      default:
        return {
          type: 'server',
          title: 'Unexpected Error',
          message: `An unexpected error occurred (${status}). Please try again.`,
          userAction: 'Retry the operation or contact support if the problem persists.',
          technicalDetails: `HTTP ${status}: ${data?.error || 'Unknown error'}`,
          retryable: true,
        };
    }
  }

  // Handle request timeout
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return {
      type: 'timeout',
      title: 'Request Timeout',
      message: 'The request took too long to complete. Please check your connection and try again.',
      userAction: 'Check your internet connection and retry.',
      technicalDetails: `Timeout: ${error.message}`,
      retryable: true,
    };
  }

  // Handle network errors (no response received)
  if (error.request && !error.response) {
    return {
      type: 'network',
      title: 'Connection Failed',
      message: 'Unable to connect to the server. Please check your internet connection.',
      userAction: 'Check your network connection and try again.',
      technicalDetails: `Network error: ${error.message}`,
      retryable: true,
    };
  }

  // Handle validation errors from our application
  if (error.name === 'ValidationError') {
    return {
      type: 'validation',
      title: 'Validation Error',
      message: error.message || 'Please check your input and try again.',
      userAction: 'Review and correct the highlighted fields.',
      retryable: false,
    };
  }

  // Handle generic errors
  return {
    type: 'unknown',
    title: 'Unexpected Error',
    message: error.message || 'An unexpected error occurred. Please try again.',
    userAction: 'Try again or contact support if the problem persists.',
    technicalDetails: error.stack || error.toString(),
    retryable: true,
  };
};

/**
 * Input validation utilities
 */
export class ValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

export const validateS3Uri = (uri: string): void => {
  if (!uri || typeof uri !== 'string') {
    throw new ValidationError('S3 URI is required');
  }

  const trimmedUri = uri.trim();
  if (!trimmedUri) {
    throw new ValidationError('S3 URI cannot be empty');
  }

  // Check S3 URI format: s3://bucket/key
  const s3UriPattern = /^s3:\/\/[a-z0-9][a-z0-9.-]*[a-z0-9]\/(.+)$/;
  if (!s3UriPattern.test(trimmedUri)) {
    throw new ValidationError('Invalid S3 URI format. Expected format: s3://bucket-name/object-key');
  }

  // Check for common issues
  if (trimmedUri.includes('//') && !trimmedUri.startsWith('s3://')) {
    throw new ValidationError('S3 URI must start with "s3://"');
  }

  if (trimmedUri.endsWith('/')) {
    throw new ValidationError('S3 URI cannot end with a forward slash');
  }
};

export const validateChatMessage = (message: string): void => {
  if (!message || typeof message !== 'string') {
    throw new ValidationError('Message is required');
  }

  const trimmedMessage = message.trim();
  if (!trimmedMessage) {
    throw new ValidationError('Message cannot be empty or contain only whitespace');
  }

  if (trimmedMessage.length > 4000) {
    throw new ValidationError('Message is too long. Please keep it under 4000 characters.');
  }
};

export const validateSessionId = (sessionId: string): void => {
  if (!sessionId || typeof sessionId !== 'string') {
    throw new ValidationError('Session ID is required');
  }

  const trimmedSessionId = sessionId.trim();
  if (!trimmedSessionId) {
    throw new ValidationError('Session ID cannot be empty');
  }

  // UUID format validation
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  if (!uuidPattern.test(trimmedSessionId)) {
    throw new ValidationError('Invalid session ID format');
  }
};

/**
 * Network connectivity utilities
 */
export const checkNetworkConnectivity = (): boolean => {
  return navigator.onLine;
};

export const waitForNetworkConnectivity = (timeout: number = 10000): Promise<boolean> => {
  return new Promise((resolve) => {
    if (navigator.onLine) {
      resolve(true);
      return;
    }

    const timeoutId = setTimeout(() => {
      window.removeEventListener('online', onlineHandler);
      resolve(false);
    }, timeout);

    const onlineHandler = () => {
      clearTimeout(timeoutId);
      window.removeEventListener('online', onlineHandler);
      resolve(true);
    };

    window.addEventListener('online', onlineHandler);
  });
};

/**
 * Retry logic utilities
 */
export interface RetryOptions {
  maxAttempts: number;
  baseDelay: number;
  maxDelay: number;
  backoffFactor: number;
}

export const defaultRetryOptions: RetryOptions = {
  maxAttempts: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  backoffFactor: 2,
};

export const withRetry = async <T>(
  operation: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> => {
  const config = { ...defaultRetryOptions, ...options };
  let lastError: any;

  for (let attempt = 1; attempt <= config.maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      const errorDetails = processError(error);

      // Don't retry non-retryable errors
      if (!errorDetails.retryable || attempt === config.maxAttempts) {
        throw error;
      }

      // Calculate delay with exponential backoff
      const delay = Math.min(
        config.baseDelay * Math.pow(config.backoffFactor, attempt - 1),
        config.maxDelay
      );

      // Safe: Using separate console.warn arguments instead of string interpolation
      // nosemgrep: unsafe-formatstring
      console.warn(`Operation failed (attempt ${attempt}/${config.maxAttempts}), retrying in ${delay}ms:`,error);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
};