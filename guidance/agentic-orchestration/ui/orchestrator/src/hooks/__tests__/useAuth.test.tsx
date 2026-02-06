// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import { describe, it, expect, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAuth } from '../useAuth';

// Mock the Amplify UI React hook
vi.mock('@aws-amplify/ui-react', () => ({
  useAuthenticator: vi.fn(() => ({
    authStatus: 'authenticated',
    user: {
      username: 'testuser',
      attributes: {
        email: 'test@example.com',
      },
    },
    signOut: vi.fn(),
  })),
}));

describe('useAuth', () => {
  it('should return authenticated user information', () => {
    const { result } = renderHook(() => useAuth());

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual({
      username: 'testuser',
      email: 'test@example.com',
      attributes: {
        email: 'test@example.com',
      },
    });
    expect(result.current.isLoading).toBe(false);
  });

  it('should provide signOut function', () => {
    const { result } = renderHook(() => useAuth());

    expect(typeof result.current.signOut).toBe('function');
  });

  it('should throw error for signIn method', async () => {
    const { result } = renderHook(() => useAuth());

    await expect(result.current.signIn('user', 'pass')).rejects.toThrow(
      'Sign in should be handled by Authenticator component'
    );
  });
});