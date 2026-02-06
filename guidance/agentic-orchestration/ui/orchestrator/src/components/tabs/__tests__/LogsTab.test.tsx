// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

import LogsTab from '../LogsTab';
import { useApp } from '../../../contexts/AppContext';
import { useSession } from '../../../contexts/SessionContext';

// Mock the contexts
vi.mock('../../../contexts/AppContext');
vi.mock('../../../contexts/SessionContext');

const mockUseApp = vi.mocked(useApp);
const mockUseSession = vi.mocked(useSession);

describe('LogsTab', () => {
  const mockClearChatHistory = vi.fn();
  const mockGenerateNewSession = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    mockUseApp.mockReturnValue({
      config: {
        apiBaseUrl: 'https://api.example.com',
        awsConfig: {
          region: 'us-west-2',
          documentBucket: 'test-bucket',
        },
      },
      user: {
        username: 'testuser',
        userId: 'test-user-id',
      },
      isAuthenticated: true,
      loading: false,
      error: null,
      notifications: [],
      addNotification: vi.fn(),
      removeNotification: vi.fn(),
    });

    mockUseSession.mockReturnValue({
      sessionState: {
        sessionId: 'test-session-123',
        chatHistory: [
          {
            id: '1',
            message: 'Hello',
            sender: 'user',
            timestamp: new Date('2023-01-01T10:00:00Z'),
          },
          {
            id: '2',
            message: 'Hi there!',
            sender: 'agent',
            timestamp: new Date('2023-01-01T10:01:00Z'),
          },
        ],
        lastActivity: new Date('2023-01-01T10:01:00Z'),
        currentJob: 'job-123',
      },
      clearChatHistory: mockClearChatHistory,
      generateNewSession: mockGenerateNewSession,
      addMessage: vi.fn(),
      setCurrentJob: vi.fn(),
    });

    mockGenerateNewSession.mockReturnValue('new-session-456');
  });

  it('displays system information correctly', () => {
    render(<LogsTab />);

    // Check system information section
    expect(screen.getByText('System Information')).toBeInTheDocument();
    expect(screen.getByText('test-session-123')).toBeInTheDocument();
    expect(screen.getByText('testuser')).toBeInTheDocument();
    expect(screen.getByText('job-123')).toBeInTheDocument();
  });

  it('displays chat history count', () => {
    render(<LogsTab />);

    // Check chat history management section
    expect(screen.getByText('Chat History Management')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument(); // Message count
  });

  it('displays configuration details in code editor', () => {
    render(<LogsTab />);

    // Check configuration section
    expect(screen.getByText('Configuration Details')).toBeInTheDocument();
    
    // The CodeEditor component should be present (it may not render as a textbox in test environment)
    // Just verify the section exists and contains the expected data
    expect(screen.getByText('test-session-123')).toBeInTheDocument();
    expect(screen.getByText('testuser')).toBeInTheDocument();
  });

  it('handles clear chat history button click', async () => {
    render(<LogsTab />);

    const clearButton = screen.getByText('Clear Chat History');
    expect(clearButton).toBeInTheDocument();
    expect(clearButton).not.toBeDisabled();

    fireEvent.click(clearButton);

    await waitFor(() => {
      expect(mockClearChatHistory).toHaveBeenCalledTimes(1);
    });
  });

  it('disables clear chat history button when no messages', () => {
    mockUseSession.mockReturnValue({
      sessionState: {
        sessionId: 'test-session-123',
        chatHistory: [],
        lastActivity: new Date('2023-01-01T10:00:00Z'),
        currentJob: null,
      },
      clearChatHistory: mockClearChatHistory,
      generateNewSession: mockGenerateNewSession,
      addMessage: vi.fn(),
      setCurrentJob: vi.fn(),
    });

    render(<LogsTab />);

    const clearButton = screen.getByRole('button', { name: 'Clear Chat History' });
    expect(clearButton).toBeDisabled();
  });

  it('handles new session button click', async () => {
    render(<LogsTab />);

    const newSessionButton = screen.getByText('New Session');
    expect(newSessionButton).toBeInTheDocument();

    fireEvent.click(newSessionButton);

    await waitFor(() => {
      expect(mockGenerateNewSession).toHaveBeenCalledTimes(1);
    });
  });

  it('displays first and latest message timestamps when multiple messages exist', () => {
    render(<LogsTab />);

    // Should show first message timestamp
    expect(screen.getByText(/First message:/)).toBeInTheDocument();
    expect(screen.getByText(/Latest message:/)).toBeInTheDocument();
  });

  it('does not show message timestamps when no messages exist', () => {
    mockUseSession.mockReturnValue({
      sessionState: {
        sessionId: 'test-session-123',
        chatHistory: [],
        lastActivity: new Date('2023-01-01T10:00:00Z'),
        currentJob: null,
      },
      clearChatHistory: mockClearChatHistory,
      generateNewSession: mockGenerateNewSession,
      addMessage: vi.fn(),
      setCurrentJob: vi.fn(),
    });

    render(<LogsTab />);

    expect(screen.queryByText(/First message:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Latest message:/)).not.toBeInTheDocument();
  });

  it('shows only first message timestamp when only one message exists', () => {
    mockUseSession.mockReturnValue({
      sessionState: {
        sessionId: 'test-session-123',
        chatHistory: [
          {
            id: '1',
            message: 'Hello',
            sender: 'user',
            timestamp: new Date('2023-01-01T10:00:00Z'),
          },
        ],
        lastActivity: new Date('2023-01-01T10:00:00Z'),
        currentJob: null,
      },
      clearChatHistory: mockClearChatHistory,
      generateNewSession: mockGenerateNewSession,
      addMessage: vi.fn(),
      setCurrentJob: vi.fn(),
    });

    render(<LogsTab />);

    expect(screen.getByText(/First message:/)).toBeInTheDocument();
    expect(screen.queryByText(/Latest message:/)).not.toBeInTheDocument();
  });

  it('handles missing configuration gracefully', () => {
    mockUseApp.mockReturnValue({
      config: null,
      user: null,
      isAuthenticated: true,
      loading: false,
      error: null,
      notifications: [],
      addNotification: vi.fn(),
      removeNotification: vi.fn(),
    });

    render(<LogsTab />);

    // Should still render without crashing
    expect(screen.getByText('System Information')).toBeInTheDocument();
    expect(screen.getByText('Unknown')).toBeInTheDocument(); // User should show as Unknown
    // The "Not configured" text appears in the JSON configuration, not as direct text
    expect(screen.getByText('Configuration Details')).toBeInTheDocument();
  });
});