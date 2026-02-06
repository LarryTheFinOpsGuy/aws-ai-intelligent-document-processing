// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { useApp } from './AppContext';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface SessionState {
  sessionId: string;
  chatHistory: ChatMessage[];
  currentJob?: string;
  lastActivity: Date;
}

interface SessionContextType {
  sessionState: SessionState;
  generateNewSession: () => string;
  assumeSession: (sessionId: string) => void;
  clearSession: () => void;
  addChatMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  clearChatHistory: () => void;
  setCurrentJob: (jobId: string | undefined) => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

interface SessionProviderProps {
  children: ReactNode;
}

export const SessionProvider: React.FC<SessionProviderProps> = ({ children }) => {
  const { apiClient } = useApp();
  const [sessionState, setSessionState] = useState<SessionState>(() => ({
    sessionId: uuidv4(),
    chatHistory: [],
    lastActivity: new Date(),
  }));

  // Update API client session ID when session changes
  useEffect(() => {
    if (apiClient && sessionState.sessionId) {
      apiClient.setSessionId(sessionState.sessionId);
    }
  }, [apiClient, sessionState.sessionId]);

  const generateNewSession = useCallback((): string => {
    const newSessionId = uuidv4();
    const newSessionState = {
      sessionId: newSessionId,
      chatHistory: [],
      lastActivity: new Date(),
    };
    
    setSessionState(newSessionState);
    
    // Update API client with new session ID
    if (apiClient) {
      apiClient.setSessionId(newSessionId);
    }
    
    return newSessionId;
  }, [apiClient]);

  const assumeSession = useCallback((sessionId: string) => {
    setSessionState(prev => ({
      ...prev,
      sessionId,
      lastActivity: new Date(),
    }));
    
    // Update API client with assumed session ID
    if (apiClient) {
      apiClient.setSessionId(sessionId);
    }
  }, [apiClient]);

  const clearSession = useCallback(() => {
    setSessionState(prev => ({
      ...prev,
      chatHistory: [],
      currentJob: undefined,
      lastActivity: new Date(),
    }));
  }, []);

  const addChatMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: uuidv4(),
      timestamp: new Date(),
    };

    setSessionState(prev => ({
      ...prev,
      chatHistory: [...prev.chatHistory, newMessage],
      lastActivity: new Date(),
    }));
  }, []);

  const clearChatHistory = useCallback(() => {
    setSessionState(prev => ({
      ...prev,
      chatHistory: [],
      lastActivity: new Date(),
    }));
  }, []);

  const setCurrentJob = useCallback((jobId: string | undefined) => {
    setSessionState(prev => ({
      ...prev,
      currentJob: jobId,
      lastActivity: new Date(),
    }));
  }, []);

  const value: SessionContextType = {
    sessionState,
    generateNewSession,
    assumeSession,
    clearSession,
    addChatMessage,
    clearChatHistory,
    setCurrentJob,
  };

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export { SessionContext };

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};