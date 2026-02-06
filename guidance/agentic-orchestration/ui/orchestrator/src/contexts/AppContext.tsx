// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuthenticator } from '@aws-amplify/ui-react';
import { Amplify } from 'aws-amplify';
import { createApiClient, ApiClient } from '../services/apiClient';

interface AppConfiguration {
  apiBaseUrl: string;
  cognitoConfig: {
    userPoolId: string;
    userPoolClientId: string;
    identityPoolId: string;
    region: string;
  };
  awsConfig: {
    region: string;
    documentBucket: string;
  };
}

interface ErrorNotification {
  id: string;
  type: 'error' | 'warning' | 'info' | 'success';
  header: string;
  content: string;
  dismissible: boolean;
  dismissLabel?: string;
  onDismiss?: () => void;
  action?: {
    buttonText: string;
    onButtonClick: () => void;
  };
}

interface AppContextType {
  config: AppConfiguration | null;
  apiClient: ApiClient | null;
  isAuthenticated: boolean;
  user: any;
  loading: boolean;
  error: string | null;
  notifications: ErrorNotification[];
  setError: (error: string | null) => void;
  addNotification: (notification: Omit<ErrorNotification, 'id' | 'onDismiss'>) => void;
  removeNotification: (index: number) => void;
  clearNotifications: () => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus, context.user]);
  const [config, setConfig] = useState<AppConfiguration | null>(null);
  const [apiClient, setApiClient] = useState<ApiClient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<ErrorNotification[]>([]);

  useEffect(() => {
    const initializeApp = async () => {
      try {
        // Load configuration from environment variables
        const appConfig: AppConfiguration = {
          apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
          cognitoConfig: {
            userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
            userPoolClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID || '',
            identityPoolId: import.meta.env.VITE_COGNITO_IDENTITY_POOL_ID || '',
            region: import.meta.env.VITE_AWS_REGION || 'us-west-2',
          },
          awsConfig: {
            region: import.meta.env.VITE_AWS_REGION || 'us-west-2',
            documentBucket: import.meta.env.VITE_DOCUMENT_BUCKET || '',
          },
        };

        // Validate required configuration
        if (!appConfig.cognitoConfig.userPoolId || !appConfig.cognitoConfig.userPoolClientId) {
          throw new Error('Missing required Cognito configuration. Please check environment variables.');
        }

        console.log('App configuration:', {
          apiBaseUrl: appConfig.apiBaseUrl,
          userPoolId: appConfig.cognitoConfig.userPoolId,
          region: appConfig.cognitoConfig.region,
        });

        // Configure Amplify
        Amplify.configure({
          Auth: {
            Cognito: {
              userPoolId: appConfig.cognitoConfig.userPoolId,
              userPoolClientId: appConfig.cognitoConfig.userPoolClientId,
              // Remove identityPoolId to avoid Identity Pool issues
              // identityPoolId: appConfig.cognitoConfig.identityPoolId,
            },
          },
        });

        // Initialize API client
        const client = createApiClient({
          baseURL: appConfig.apiBaseUrl,
          timeout: 30000,
        });

        setConfig(appConfig);
        setApiClient(client);
      } catch (err) {
        console.error('Failed to initialize app:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to initialize application';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    initializeApp();
  }, []);

  const addNotification = (notification: Omit<ErrorNotification, 'id' | 'onDismiss'>) => {
    const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const fullNotification: ErrorNotification = {
      ...notification,
      id,
      onDismiss: () => removeNotification(id),
    };
    setNotifications(prev => [...prev, fullNotification]);
    
    // Auto-dismiss success and info notifications after 5 seconds
    if (notification.type === 'success' || notification.type === 'info') {
      setTimeout(() => {
        removeNotification(id);
      }, 5000);
    }
  };

  const removeNotification = (id: string) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  };

  const clearNotifications = () => {
    setNotifications([]);
  };

  const value: AppContextType = {
    config,
    apiClient,
    isAuthenticated: authStatus === 'authenticated',
    user,
    loading,
    error,
    notifications,
    setError,
    addNotification,
    removeNotification,
    clearNotifications,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};