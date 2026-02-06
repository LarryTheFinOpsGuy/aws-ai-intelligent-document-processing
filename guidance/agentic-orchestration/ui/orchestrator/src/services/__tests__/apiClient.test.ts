// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiClient, createApiClient, getApiClient, resetApiClient, isApiClientInitialized } from '../ApiClient';
import type { ApiClientOptions } from '../ApiClient';

// Mock aws-amplify/auth
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(() =>
    Promise.resolve({
      tokens: {
        idToken: {
          toString: () => 'mock-id-token',
        },
      },
    })
  ),
}));

// Mock error handling utilities
vi.mock('../../utils/errorHandling', () => ({
  processError: vi.fn((error) => ({
    type: 'server',
    title: 'Server Error',
    message: error.message || 'An error occurred',
    retryable: true,
  })),
  withRetry: vi.fn((operation) => operation()),
  checkNetworkConnectivity: vi.fn(() => true),
}));

// Mock axios
const mockAxiosInstance = {
  interceptors: {
    request: {
      use: vi.fn(),
    },
    response: {
      use: vi.fn(),
    },
  },
  defaults: {
    baseURL: 'http://localhost:3000/api',
    timeout: 30000,
  },
  get: vi.fn(),
  post: vi.fn(),
  request: vi.fn(),
};

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockAxiosInstance),
  },
}));

describe('ApiClient', () => {
  let apiClient: ApiClient;
  const mockConfig: ApiClientOptions = {
    baseURL: 'http://localhost:3000/api',
    timeout: 5000,
    enableRequestLogging: true,
    enableResponseLogging: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    apiClient = new ApiClient(mockConfig);
  });

  afterEach(() => {
    resetApiClient();
  });

  describe('Constructor and Configuration', () => {
    it('should create an instance with correct configuration', () => {
      expect(apiClient).toBeInstanceOf(ApiClient);
    });

    it('should set up interceptors during construction', () => {
      expect(mockAxiosInstance.interceptors.request.use).toHaveBeenCalled();
      expect(mockAxiosInstance.interceptors.response.use).toHaveBeenCalled();
    });

    it('should use default options when not provided', () => {
      const basicClient = new ApiClient({ baseURL: 'http://test.com' });
      expect(basicClient).toBeInstanceOf(ApiClient);
    });
  });

  describe('Session Management', () => {
    it('should set and get session ID', () => {
      const sessionId = 'test-session-id-123';
      
      apiClient.setSessionId(sessionId);
      expect(apiClient.getSessionId()).toBe(sessionId);
    });

    it('should clear session ID', () => {
      const sessionId = 'test-session-id-123';
      
      apiClient.setSessionId(sessionId);
      expect(apiClient.getSessionId()).toBe(sessionId);
      
      apiClient.clearSessionId();
      expect(apiClient.getSessionId()).toBeNull();
    });

    it('should return null for session ID initially', () => {
      expect(apiClient.getSessionId()).toBeNull();
    });
  });

  describe('API Methods', () => {
    beforeEach(() => {
      mockAxiosInstance.request.mockResolvedValue({
        data: { success: true },
        status: 200,
      });
    });

    it('should have all required API methods', () => {
      expect(typeof apiClient.getJobs).toBe('function');
      expect(typeof apiClient.getJobActions).toBe('function');
      expect(typeof apiClient.sendChatMessage).toBe('function');
      expect(typeof apiClient.healthCheck).toBe('function');
      expect(typeof apiClient.startProcessing).toBe('function');
    });

    it('should call getJobs with correct parameters', async () => {
      const mockResponse = {
        jobs: [],
        total_count: 0,
        has_more: false,
      };
      
      mockAxiosInstance.request.mockResolvedValue({
        data: mockResponse,
        status: 200,
      });

      const result = await apiClient.getJobs(5);
      
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'get',
          url: '/jobs',
          params: { limit: 5 },
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should call getJobActions with correct job ID', async () => {
      const jobId = 'test-job-123';
      const mockResponse = {
        job_id: jobId,
        actions: [],
        job_details: {} as any,
      };
      
      mockAxiosInstance.request.mockResolvedValue({
        data: mockResponse,
        status: 200,
      });

      const result = await apiClient.getJobActions(jobId);
      
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'get',
          url: `/jobs/${jobId}/actions`,
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should validate job ID in getJobActions', async () => {
      await expect(apiClient.getJobActions('')).rejects.toThrow('Job ID is required');
      await expect(apiClient.getJobActions(null as any)).rejects.toThrow('Job ID is required');
    });

    it('should call sendChatMessage with correct message', async () => {
      const message = 'Hello, how can I help?';
      const mockResponse = {
        message: 'Response message',
        sessionId: 'session-123',
        timestamp: '2023-01-01T00:00:00Z',
      };
      
      mockAxiosInstance.request.mockResolvedValue({
        data: mockResponse,
        status: 200,
      });

      const result = await apiClient.sendChatMessage(message);
      
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'post',
          url: '/chat',
          data: {
            message: message,
            action: 'chat',
          },
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should validate chat message input', async () => {
      await expect(apiClient.sendChatMessage('')).rejects.toThrow('Message is required and must be a string');
      await expect(apiClient.sendChatMessage('   ')).rejects.toThrow('Message cannot be empty');
      await expect(apiClient.sendChatMessage(null as any)).rejects.toThrow('Message is required and must be a string');
    });

    it('should validate S3 URI in startProcessing', async () => {
      await expect(apiClient.startProcessing('')).rejects.toThrow('S3 URI is required');
      await expect(apiClient.startProcessing('invalid-uri')).rejects.toThrow('Invalid S3 URI format');
      await expect(apiClient.startProcessing('http://example.com')).rejects.toThrow('Invalid S3 URI format');
    });

    it('should accept valid S3 URI in startProcessing', async () => {
      const s3Uri = 's3://my-bucket/my-file.pdf';
      const mockResponse = {
        job_id: 'job-123',
        status: 'started',
      };
      
      mockAxiosInstance.request.mockResolvedValue({
        data: mockResponse,
        status: 200,
      });

      const result = await apiClient.startProcessing(s3Uri);
      
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: 'post',
          url: '/orchestrate',
          data: {
            s3_uri: s3Uri,
          },
        })
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe('Utility Methods', () => {
    it('should return base URL', () => {
      expect(apiClient.getBaseURL()).toBe(mockAxiosInstance.defaults.baseURL);
    });

    it('should return timeout', () => {
      expect(apiClient.getTimeout()).toBe(mockAxiosInstance.defaults.timeout);
    });

    it('should update configuration', () => {
      const newConfig = {
        baseURL: 'http://new-url.com',
        timeout: 60000,
        enableRequestLogging: false,
      };

      apiClient.updateConfig(newConfig);
      
      expect(mockAxiosInstance.defaults.baseURL).toBe(newConfig.baseURL);
      expect(mockAxiosInstance.defaults.timeout).toBe(newConfig.timeout);
    });
  });

  describe('Singleton Management', () => {
    it('should create and get singleton instance', () => {
      resetApiClient();
      expect(isApiClientInitialized()).toBe(false);
      
      const client = createApiClient(mockConfig);
      expect(isApiClientInitialized()).toBe(true);
      expect(getApiClient()).toBe(client);
    });

    it('should throw error when getting uninitialized client', () => {
      resetApiClient();
      expect(() => getApiClient()).toThrow('API client not initialized');
    });

    it('should reset singleton instance', () => {
      createApiClient(mockConfig);
      expect(isApiClientInitialized()).toBe(true);
      
      resetApiClient();
      expect(isApiClientInitialized()).toBe(false);
    });
  });
});