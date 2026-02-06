// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import axios, { AxiosInstance, AxiosResponse, AxiosRequestConfig } from 'axios';
import { fetchAuthSession } from 'aws-amplify/auth';
import { processError, withRetry, checkNetworkConnectivity, RetryOptions } from '../utils/errorHandling';
import {
  ApiClientConfig,
  JobListResponse,
  JobActionsResponse,
  JobFlowResponse,
  ChatResponse,
  CreateJobResponse,
  ProcessingJob,
} from '../types';

// Extend AxiosRequestConfig to include metadata
declare module 'axios' {
  interface AxiosRequestConfig {
    metadata?: {
      requestId: string;
      startTime: number;
    };
  }
}

// Extended interfaces for API client specific functionality
export interface ApiRequestConfig extends AxiosRequestConfig {
  retryOptions?: Partial<RetryOptions>;
  skipRetry?: boolean;
}

export interface ApiClientOptions extends ApiClientConfig {
  enableRequestLogging?: boolean;
  enableResponseLogging?: boolean;
  defaultRetryOptions?: Partial<RetryOptions>;
}

export interface RequestLogEntry {
  timestamp: string;
  method: string;
  url: string;
  fullUrl: string;
  headers: Record<string, string>;
  sessionId?: string;
  tokenAvailable: boolean;
  requestId: string;
}

export interface ResponseLogEntry {
  timestamp: string;
  requestId: string;
  status: number;
  url: string;
  responseTime: number;
  dataSize: number;
  success: boolean;
}

export interface ErrorLogEntry {
  timestamp: string;
  requestId: string;
  status?: number;
  url: string;
  message: string;
  errorType: string;
  networkOnline: boolean;
  retryAttempt?: number;
}

export class ApiClient {
  private client: AxiosInstance;
  private sessionId: string | null = null;
  private options: ApiClientOptions;
  private requestCounter = 0;
  private requestTimes = new Map<string, number>();

  constructor(config: ApiClientOptions) {
    this.options = {
      enableRequestLogging: true,
      enableResponseLogging: true,
      defaultRetryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
        maxDelay: 10000,
        backoffFactor: 2,
      },
      ...config,
    };

    this.client = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
      },
      // Add CORS configuration
      withCredentials: false,
    });

    this.setupInterceptors();
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${++this.requestCounter}`;
  }

  private setupInterceptors(): void {
    // Request interceptor to add authentication and session headers
    this.client.interceptors.request.use(
      async (config) => {
        const requestId = this.generateRequestId();
        config.metadata = { requestId, startTime: Date.now() };
        this.requestTimes.set(requestId, Date.now());

        try {
          // Get the current auth session
          const session = await fetchAuthSession();
          // Use ID token for Cognito User Pool authorizer
          const token = session.tokens?.idToken?.toString();
          
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }

          // Add session ID if available
          if (this.sessionId) {
            config.headers['X-Session-Id'] = this.sessionId;
          }

          // Add request ID for tracking
          config.headers['X-Request-Id'] = requestId;

          // Enhanced request logging
          if (this.options.enableRequestLogging) {
            const logEntry: RequestLogEntry = {
              timestamp: new Date().toISOString(),
              method: config.method?.toUpperCase() || 'GET',
              url: config.url || '',
              fullUrl: `${config.baseURL}${config.url}`,
              headers: {
                Authorization: config.headers.Authorization ? 'Bearer [REDACTED]' : 'None',
                'Content-Type': String(config.headers['Content-Type'] || 'None'),
              },
              sessionId: this.sessionId || undefined,
              tokenAvailable: !!token,
              requestId,
            };

            console.log('🚀 API Request:', logEntry);
            console.log('🚀 Full Request Config:', {
              method: config.method,
              url: config.url,
              params: config.params,
              data: config.data,
              baseURL: config.baseURL,
              fullURL: `${config.baseURL}${config.url}${config.params ? '?' + new URLSearchParams(config.params).toString() : ''}`,
            });

            // Log request body for debugging (excluding sensitive data)
            if (config.data && config.method?.toLowerCase() !== 'get') {
              const sanitizedData = this.sanitizeRequestData(config.data);
              console.log('📤 Request Body:', sanitizedData);
            }
          }

          return config;
        } catch (error) {
          console.error('❌ Failed to add auth headers:', error);
          return config;
        }
      },
      (error) => {
        console.error('❌ Request interceptor error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling and logging
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        const requestId = response.config.metadata?.requestId;
        const startTime = requestId ? this.requestTimes.get(requestId) : undefined;
        const responseTime = startTime ? Date.now() - startTime : 0;

        if (requestId) {
          this.requestTimes.delete(requestId);
        }

        if (this.options.enableResponseLogging) {
          const logEntry: ResponseLogEntry = {
            timestamp: new Date().toISOString(),
            requestId: requestId || 'unknown',
            status: response.status,
            url: response.config.url || '',
            responseTime,
            dataSize: JSON.stringify(response.data).length,
            success: true,
          };

          console.log('✅ API Response:', logEntry);

          // Log response data structure for debugging
          if (response.data) {
            console.log('📥 Response Data Structure:', this.getDataStructure(response.data));
          }
        }

        return response;
      },
      (error) => {
        const requestId = error.config?.metadata?.requestId;

        if (requestId) {
          this.requestTimes.delete(requestId);
        }

        const errorLogEntry: ErrorLogEntry = {
          timestamp: new Date().toISOString(),
          requestId: requestId || 'unknown',
          status: error.response?.status,
          url: error.config?.url || '',
          message: error.message,
          errorType: error.response ? 'HTTP_ERROR' : 'NETWORK_ERROR',
          networkOnline: checkNetworkConnectivity(),
        };

        console.error('❌ API Error:', errorLogEntry);

        // Log error response data if available
        if (error.response?.data) {
          console.error('📥 Error Response Data:', error.response.data);
        }

        // Use comprehensive error processing
        const errorDetails = processError(error);
        const enhancedError = new Error(errorDetails.message);
        (enhancedError as any).details = errorDetails;
        (enhancedError as any).requestId = requestId;
        throw enhancedError;
      }
    );
  }

  private sanitizeRequestData(data: any): any {
    if (typeof data !== 'object' || data === null) {
      return data;
    }

    const sanitized = { ...data };
    
    // Remove or redact sensitive fields
    const sensitiveFields = ['password', 'token', 'secret', 'key', 'auth'];
    for (const field of sensitiveFields) {
      if (field in sanitized) {
        sanitized[field] = '[REDACTED]';
      }
    }

    return sanitized;
  }

  private getDataStructure(data: any): any {
    if (Array.isArray(data)) {
      return {
        type: 'array',
        length: data.length,
        firstItem: data.length > 0 ? this.getDataStructure(data[0]) : null,
      };
    }

    if (typeof data === 'object' && data !== null) {
      const structure: Record<string, any> = {};
      for (const key in data) {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
          structure[key] = typeof data[key];
        }
      }
      return { type: 'object', keys: Object.keys(data), structure };
    }

    return { type: typeof data, value: data };
  }

  /**
   * Session management methods
   */
  setSessionId(sessionId: string): void {
    this.sessionId = sessionId;
    console.log('🔄 Session ID updated:', sessionId);
  }

  clearSessionId(): void {
    const previousSessionId = this.sessionId;
    this.sessionId = null;
    console.log('🗑️ Session ID cleared:', previousSessionId);
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Generic request method with enhanced retry logic and error handling
   */
  private async makeRequest<T>(
    method: 'get' | 'post' | 'put' | 'patch' | 'delete',
    url: string,
    data?: any,
    config?: ApiRequestConfig
  ): Promise<T> {
    const retryOptions = {
      ...this.options.defaultRetryOptions,
      ...config?.retryOptions,
    };

    const operation = async (): Promise<T> => {
      const requestConfig: AxiosRequestConfig = {
        method,
        url,
        ...config,
        ...(data && { data }),
      };

      // Remove retryOptions from the axios config as it's not a valid axios option
      delete (requestConfig as any).retryOptions;

      const response = await this.client.request<T>(requestConfig);
      return response.data;
    };

    if (config?.skipRetry) {
      return operation();
    }

    return withRetry(operation, retryOptions);
  }

  /**
   * Job management API methods
   */
  async getJobs(limit: number = 10, status: string = 'COMPLETED'): Promise<JobListResponse> {
    console.log('📋 Fetching jobs list with limit:', limit, 'status:', status);
    
    return this.makeRequest<JobListResponse>('get', '/jobs', undefined, {
      params: { limit, status },
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async getJobActions(jobId: string): Promise<JobActionsResponse> {
    console.log('🔍 Fetching job actions for job:', jobId);
    
    if (!jobId || typeof jobId !== 'string') {
      throw new Error('Job ID is required and must be a string');
    }

    return this.makeRequest<JobActionsResponse>('get', `/jobs/${encodeURIComponent(jobId)}/actions`, undefined, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async getJobFlow(jobId: string): Promise<JobFlowResponse> {
    console.log('🔍 Fetching job flow for job:', jobId);
    
    if (!jobId || typeof jobId !== 'string') {
      throw new Error('Job ID is required and must be a string');
    }

    return this.makeRequest<JobFlowResponse>('get', `/jobs/${encodeURIComponent(jobId)}/flow`, undefined, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async searchJob(jobId: string): Promise<{ job: ProcessingJob }> {
    console.log('🔍 Searching for job:', jobId);
    
    if (!jobId || typeof jobId !== 'string') {
      throw new Error('Job ID is required and must be a string');
    }

    return this.makeRequest<{ job: ProcessingJob }>('get', '/jobs/search', undefined, {
      params: { job_id: jobId },
      retryOptions: {
        maxAttempts: 2,
        baseDelay: 1000,
      },
    });
  }

  /**
   * Chat API methods
   */
  async sendChatMessage(message: string): Promise<ChatResponse> {
    if (!message || typeof message !== 'string') {
      throw new Error('Message is required and must be a string');
    }

    console.log('💬 Sending chat message, length:', message.length);
    
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      throw new Error('Message cannot be empty or contain only whitespace');
    }

    return this.makeRequest<ChatResponse>('post', '/chat', {
      message: trimmedMessage,
      action: 'chat',
    }, {
      retryOptions: {
        maxAttempts: 2, // Fewer retries for chat to avoid duplicate messages
        baseDelay: 500,
      },
    });
  }

  /**
   * Health check and connectivity methods
   */
  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    console.log('🏥 Performing health check');
    
    return this.makeRequest<{ status: string; timestamp: string }>('get', '/health', undefined, {
      skipRetry: true,
      timeout: 5000,
    });
  }

  /**
   * Job creation method
   */
  async createJob(s3Uri: string): Promise<CreateJobResponse> {
    console.log('🚀 Creating job for document:', s3Uri);
    
    if (!s3Uri || typeof s3Uri !== 'string') {
      throw new Error('S3 URI is required and must be a string');
    }

    const s3UriPattern = /^s3:\/\/[a-z0-9][a-z0-9.-]*[a-z0-9]\/(.+)$/;
    if (!s3UriPattern.test(s3Uri)) {
      throw new Error('Invalid S3 URI format. Expected format: s3://bucket-name/object-key');
    }

    return this.makeRequest<CreateJobResponse>('post', '/orchestrate', {
      s3_uri: s3Uri,
    }, {
      retryOptions: {
        maxAttempts: 2,
        baseDelay: 2000,
      },
    });
  }

  /**
   * Processing Rules API methods
   */
  async getProcessingRules(limit: number = 100, nextToken?: string): Promise<any> {
    console.log('📋 Fetching processing rules with limit:', limit);
    
    const params: any = { limit };
    if (nextToken) {
      params.nextToken = nextToken;
    }

    return this.makeRequest<any>('get', '/processing-rules', undefined, {
      params,
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async searchProcessingRules(searchParams: { sender_name: string; document_type?: string; status?: string }): Promise<any> {
    console.log('🔍 Searching processing rules:', searchParams);
    
    if (!searchParams.sender_name) {
      throw new Error('sender_name is required for search');
    }

    return this.makeRequest<any>('post', '/processing-rules/search', searchParams, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async getProcessingRule(id: string): Promise<any> {
    console.log('🔍 Fetching processing rule:', id);
    
    if (!id || typeof id !== 'string') {
      throw new Error('Rule ID is required and must be a string');
    }

    return this.makeRequest<any>('get', `/processing-rules/${encodeURIComponent(id)}`, undefined, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async updateProcessingRule(id: string, updates: { status: string }): Promise<any> {
    console.log('🔄 Updating processing rule:', id, updates);
    
    if (!id || typeof id !== 'string') {
      throw new Error('Rule ID is required and must be a string');
    }

    if (!updates.status || !['ACTIVE', 'PENDING REVIEW', 'ARCHIVED'].includes(updates.status)) {
      throw new Error('Status must be ACTIVE, PENDING REVIEW, or ARCHIVED');
    }

    return this.makeRequest<any>('patch', `/processing-rules/${encodeURIComponent(id)}`, updates, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  /**
   * @deprecated Use createJob instead
   */
  async startProcessing(s3Uri: string): Promise<{ job_id: string; status: string }> {
    console.log('🚀 Starting document processing for:', s3Uri);
    
    if (!s3Uri || typeof s3Uri !== 'string') {
      throw new Error('S3 URI is required and must be a string');
    }

    // Validate S3 URI format
    const s3UriPattern = /^s3:\/\/[a-z0-9][a-z0-9.-]*[a-z0-9]\/(.+)$/;
    if (!s3UriPattern.test(s3Uri)) {
      throw new Error('Invalid S3 URI format. Expected format: s3://bucket-name/object-key');
    }

    return this.makeRequest<{ job_id: string; status: string }>('post', '/orchestrate', {
      s3_uri: s3Uri,
    }, {
      retryOptions: {
        maxAttempts: 2,
        baseDelay: 2000,
      },
    });
  }

  /**
   * Utility methods
   */
  getBaseURL(): string {
    return this.client.defaults.baseURL || '';
  }

  getTimeout(): number {
    return this.client.defaults.timeout || 30000;
  }

  updateConfig(config: Partial<ApiClientOptions>): void {
    this.options = { ...this.options, ...config };
    
    if (config.baseURL) {
      this.client.defaults.baseURL = config.baseURL;
    }
    
    if (config.timeout) {
      this.client.defaults.timeout = config.timeout;
    }

    console.log('⚙️ API client configuration updated:', config);
  }

  /**
   * Instructions management methods
   */
  async getInstructionsContent(s3Key: string): Promise<{ content: string }> {
    console.log('📄 Getting instructions content for:', s3Key);
    
    if (!s3Key || typeof s3Key !== 'string') {
      throw new Error('S3 key is required and must be a string');
    }

    return this.makeRequest<{ content: string }>('post', '/processing-rules/s3-bucket', {
      tool_name: 'download_file',
      file_key: s3Key
    }, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  async saveInstructionsContent(s3Key: string, content: string): Promise<{ success: boolean }> {
    console.log('💾 Saving instructions content for:', s3Key);
    
    if (!s3Key || typeof s3Key !== 'string') {
      throw new Error('S3 key is required and must be a string');
    }

    if (!content || typeof content !== 'string') {
      throw new Error('Content is required and must be a string');
    }

    return this.makeRequest<{ success: boolean }>('post', '/processing-rules/s3-bucket', {
      tool_name: 'upload_file',
      file_key: s3Key,
      file_content: content,
      content_type: 'text/markdown'
    }, {
      retryOptions: {
        maxAttempts: 3,
        baseDelay: 1000,
      },
    });
  }

  /**
   * Get document content from S3
   */
  async getDocumentContent(s3Key: string): Promise<{ content: string }> {
    console.log('📄 Getting document content for:', s3Key);
    
    if (!s3Key || typeof s3Key !== 'string') {
      throw new Error('S3 key is required and must be a string');
    }

    return this.makeRequest<{ content: string }>('post', '/processing-rules/s3-bucket', {
      tool_name: 'download_file',
      file_key: s3Key
    });
  }

  /**
   * Get processing rule by document ID
   */
  async getProcessingRuleByDocId(docId: string): Promise<any> {
    console.log('📋 Getting processing rule for doc ID:', docId);
    
    if (!docId || typeof docId !== 'string') {
      throw new Error('Document ID is required and must be a string');
    }

    return this.makeRequest<any>('get', `/processing-rules/${docId}`);
  }
}

/**
 * Singleton instance management
 */
let apiClientInstance: ApiClient | null = null;

export const createApiClient = (config: ApiClientOptions): ApiClient => {
  console.log('🏗️ Creating new API client instance with config:', {
    baseURL: config.baseURL,
    timeout: config.timeout,
    enableRequestLogging: config.enableRequestLogging,
    enableResponseLogging: config.enableResponseLogging,
  });
  
  apiClientInstance = new ApiClient(config);
  return apiClientInstance;
};

export const getApiClient = (): ApiClient => {
  if (!apiClientInstance) {
    throw new Error('API client not initialized. Call createApiClient first.');
  }
  return apiClientInstance;
};

export const resetApiClient = (): void => {
  console.log('🔄 Resetting API client instance');
  apiClientInstance = null;
};

/**
 * Convenience method to check if API client is initialized
 */
export const isApiClientInitialized = (): boolean => {
  return apiClientInstance !== null;
};

/**
 * ApiClient class is already exported above in the class declaration
 * No need for additional export statement
 */