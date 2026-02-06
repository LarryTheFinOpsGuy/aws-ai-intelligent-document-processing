// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Authenticator } from '@aws-amplify/ui-react';

import ChatTab from '../ChatTab';
import { AppProvider } from '../../../contexts/AppContext';
import { SessionProvider } from '../../../contexts/SessionContext';

// Mock the API client
const mockApiClient = {
  getJobs: vi.fn(),
  getJobActions: vi.fn(),
  sendChatMessage: vi.fn(),
  setSessionId: vi.fn(),
  clearSessionId: vi.fn(),
};

vi.mock('../../../services/apiClient', () => ({
  createApiClient: vi.fn(() => mockApiClient),
  getApiClient: vi.fn(() => mockApiClient),
}));

// Mock AWS Amplify auth
vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(() => Promise.resolve({
    tokens: {
      accessToken: { toString: () => 'mock-access-token' },
      idToken: { toString: () => 'mock-id-token' },
    },
  })),
}));

// Mock scrollIntoView for testing environment
Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  value: vi.fn(),
  writable: true,
});

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <Authenticator.Provider>
      <AppProvider>
        <SessionProvider>
          {children}
        </SessionProvider>
      </AppProvider>
    </Authenticator.Provider>
  </BrowserRouter>
);

describe('ChatTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the chat interface', () => {
    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    expect(screen.getByText('Agent Chat')).toBeInTheDocument();
    expect(screen.getByText('Chat with the AI agent for assistance and guidance')).toBeInTheDocument();
  });

  it('displays welcome message when no chat history exists', () => {
    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    expect(screen.getByText('Welcome to Agent Chat')).toBeInTheDocument();
    expect(screen.getByText(/Start a conversation with the AI agent/)).toBeInTheDocument();
  });

  it('has input field and send button', () => {
    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    const input = screen.getByPlaceholderText('Type your message here...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    expect(input).toBeInTheDocument();
    expect(sendButton).toBeInTheDocument();
    expect(sendButton).toBeDisabled(); // Should be disabled when input is empty
  });

  it('enables send button when message is typed', () => {
    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    const input = screen.getByPlaceholderText('Type your message here...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    fireEvent.change(input, { target: { value: 'Hello' } });
    
    expect(sendButton).not.toBeDisabled();
  });

  it('sends message when send button is clicked', async () => {
    mockApiClient.sendChatMessage.mockResolvedValue({
      message: 'Hello! How can I help you?',
      timestamp: new Date().toISOString(),
      session_id: 'test-session',
    });

    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    const input = screen.getByPlaceholderText('Type your message here...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockApiClient.sendChatMessage).toHaveBeenCalledWith('Hello');
    });

    // Check that user message appears
    await waitFor(() => {
      expect(screen.getByText('You')).toBeInTheDocument();
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    // Check that agent response appears
    await waitFor(() => {
      expect(screen.getByText('AI Agent')).toBeInTheDocument();
      expect(screen.getByText('Hello! How can I help you?')).toBeInTheDocument();
    });
  });

  it('sends message when Enter key is pressed', async () => {
    mockApiClient.sendChatMessage.mockResolvedValue({
      message: 'Response to Enter key',
      timestamp: new Date().toISOString(),
      session_id: 'test-session',
    });

    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    const input = screen.getByPlaceholderText('Type your message here...');
    
    // Use userEvent for more realistic interaction
    await userEvent.type(input, 'Test message');
    await userEvent.keyboard('{Enter}');

    await waitFor(() => {
      expect(mockApiClient.sendChatMessage).toHaveBeenCalledWith('Test message');
    });
  });

  it('handles API errors gracefully', async () => {
    mockApiClient.sendChatMessage.mockRejectedValue(new Error('API Error'));

    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    const input = screen.getByPlaceholderText('Type your message here...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText(/Sorry, I encountered an error/)).toBeInTheDocument();
    });
  });

  it('has clear history button', () => {
    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    const clearButton = screen.getByRole('button', { name: /clear history/i });
    expect(clearButton).toBeInTheDocument();
    expect(clearButton).toBeDisabled(); // Should be disabled when no history
  });

  it('displays session information', () => {
    render(
      <TestWrapper>
        <ChatTab />
      </TestWrapper>
    );

    expect(screen.getByText(/Session ID:/)).toBeInTheDocument();
    expect(screen.getByText(/Messages:/)).toBeInTheDocument();
  });
});