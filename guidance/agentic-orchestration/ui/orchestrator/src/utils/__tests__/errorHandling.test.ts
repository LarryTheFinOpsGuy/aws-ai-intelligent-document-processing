// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect } from 'vitest';
import { 
  processError, 
  validateS3Uri, 
  validateChatMessage, 
  validateSessionId,
  ValidationError,
  checkNetworkConnectivity,
  withRetry
} from '../errorHandling';

describe('Error Handling Utilities', () => {
  describe('processError', () => {
    it('handles network errors correctly', () => {
      const networkError = { request: {}, message: 'Network Error' };
      const result = processError(networkError);
      
      expect(result.type).toBe('network');
      expect(result.title).toBe('Connection Failed');
      expect(result.retryable).toBe(true);
    });

    it('handles 401 authentication errors', () => {
      const authError = { response: { status: 401, data: { error: 'Unauthorized' } } };
      const result = processError(authError);
      
      expect(result.type).toBe('authentication');
      expect(result.title).toBe('Authentication Required');
      expect(result.retryable).toBe(false);
    });

    it('handles 500 server errors', () => {
      const serverError = { response: { status: 500, data: { error: 'Internal Server Error' } } };
      const result = processError(serverError);
      
      expect(result.type).toBe('server');
      expect(result.title).toBe('Server Error');
      expect(result.retryable).toBe(true);
    });

    it('handles timeout errors', () => {
      const timeoutError = { code: 'ECONNABORTED', message: 'timeout of 5000ms exceeded' };
      const result = processError(timeoutError);
      
      expect(result.type).toBe('timeout');
      expect(result.title).toBe('Request Timeout');
      expect(result.retryable).toBe(true);
    });
  });

  describe('Input Validation', () => {
    describe('validateS3Uri', () => {
      it('accepts valid S3 URIs', () => {
        expect(() => validateS3Uri('s3://my-bucket/my-file.pdf')).not.toThrow();
        expect(() => validateS3Uri('s3://test-bucket-123/folder/file.txt')).not.toThrow();
      });

      it('rejects invalid S3 URIs', () => {
        expect(() => validateS3Uri('')).toThrow(ValidationError);
        expect(() => validateS3Uri('http://example.com')).toThrow(ValidationError);
        expect(() => validateS3Uri('s3://bucket')).toThrow(ValidationError);
        expect(() => validateS3Uri('s3://bucket/')).toThrow(ValidationError);
      });
    });

    describe('validateChatMessage', () => {
      it('accepts valid messages', () => {
        expect(() => validateChatMessage('Hello world')).not.toThrow();
        expect(() => validateChatMessage('A longer message with multiple words')).not.toThrow();
      });

      it('rejects invalid messages', () => {
        expect(() => validateChatMessage('')).toThrow(ValidationError);
        expect(() => validateChatMessage('   ')).toThrow(ValidationError);
        expect(() => validateChatMessage('a'.repeat(5000))).toThrow(ValidationError);
      });
    });

    describe('validateSessionId', () => {
      it('accepts valid UUIDs', () => {
        expect(() => validateSessionId('123e4567-e89b-12d3-a456-426614174000')).not.toThrow();
        expect(() => validateSessionId('550e8400-e29b-41d4-a716-446655440000')).not.toThrow();
      });

      it('rejects invalid session IDs', () => {
        expect(() => validateSessionId('')).toThrow(ValidationError);
        expect(() => validateSessionId('not-a-uuid')).toThrow(ValidationError);
        expect(() => validateSessionId('123-456-789')).toThrow(ValidationError);
      });
    });
  });

  describe('Network Utilities', () => {
    it('checks network connectivity', () => {
      const result = checkNetworkConnectivity();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('Retry Logic', () => {
    it('retries failed operations', async () => {
      let attempts = 0;
      const operation = async () => {
        attempts++;
        if (attempts < 3) {
          throw new Error('Temporary failure');
        }
        return 'success';
      };

      const result = await withRetry(operation, { maxAttempts: 3, baseDelay: 10 });
      expect(result).toBe('success');
      expect(attempts).toBe(3);
    });

    it('gives up after max attempts', async () => {
      const operation = async () => {
        throw new Error('Persistent failure');
      };

      await expect(withRetry(operation, { maxAttempts: 2, baseDelay: 10 }))
        .rejects.toThrow('Persistent failure');
    });
  });
});