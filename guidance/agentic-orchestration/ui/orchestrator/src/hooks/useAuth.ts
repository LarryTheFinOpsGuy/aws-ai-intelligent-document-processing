// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import { useAuthenticator } from '@aws-amplify/ui-react';
import { useCallback } from 'react';

export interface AuthUser {
  username: string;
  email?: string;
  attributes?: Record<string, any>;
}

export interface UseAuthReturn {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  signOut: () => void;
  signIn: (username: string, password: string) => Promise<void>;
}

export const useAuth = (): UseAuthReturn => {
  const { authStatus, user, signOut: amplifySignOut } = useAuthenticator(context => [
    context.authStatus,
    context.user,
    context.signOut,
  ]);

  const isAuthenticated = authStatus === 'authenticated';
  const isLoading = authStatus === 'configuring';

  const signOut = useCallback(() => {
    amplifySignOut();
  }, [amplifySignOut]);

  const signIn = useCallback(async (_username: string, _password: string) => {
    // This will be handled by the Authenticator component
    // We're keeping this for future custom implementation if needed
    throw new Error('Sign in should be handled by Authenticator component');
  }, []);

  const authUser: AuthUser | null = user
    ? {
        username: user.username,
        email: user.attributes?.email,
        attributes: user.attributes,
      }
    : null;

  return {
    user: authUser,
    isAuthenticated,
    isLoading,
    signOut,
    signIn,
  };
};