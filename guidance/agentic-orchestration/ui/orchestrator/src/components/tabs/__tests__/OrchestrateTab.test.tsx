// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Authenticator } from '@aws-amplify/ui-react';

import OrchestrateTab from '../OrchestrateTab';
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

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
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

const renderWithWrapper = (component: React.ReactElement) => {
  return render(
    <TestWrapper>
      {component}
    </TestWrapper>
  );
};

describe('OrchestrateTab', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('renders the placeholder interface with future functionality message', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    // Check for main header
    expect(screen.getByText('Orchestrate Documents')).toBeInTheDocument();
    
    // Check for placeholder message
    expect(screen.getByText('Orchestration Features Coming Soon')).toBeInTheDocument();
    expect(screen.getByText(/Document processing orchestration functionality will be implemented/)).toBeInTheDocument();
  });

  it('displays planned features information', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    // Check for planned features section
    expect(screen.getByText('Planned Features')).toBeInTheDocument();
    expect(screen.getByText('Document Upload')).toBeInTheDocument();
    expect(screen.getByText('Workflow Configuration')).toBeInTheDocument();
    expect(screen.getByText('Job Creation')).toBeInTheDocument();
    expect(screen.getByText('Instructions Management')).toBeInTheDocument();
  });

  it('provides navigation buttons to other functional tabs', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    // Check for navigation buttons
    const statusButton = screen.getByText('Monitor Job Status');
    const chatButton = screen.getByText('Chat with AI Agent');
    
    expect(statusButton).toBeInTheDocument();
    expect(chatButton).toBeInTheDocument();
  });

  it('navigates to status tab when status button is clicked', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    const statusButton = screen.getByText('Monitor Job Status');
    fireEvent.click(statusButton);
    
    expect(mockNavigate).toHaveBeenCalledWith('/status');
  });

  it('navigates to chat tab when chat button is clicked', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    const chatButton = screen.getByText('Chat with AI Agent');
    fireEvent.click(chatButton);
    
    expect(mockNavigate).toHaveBeenCalledWith('/chat');
  });

  it('maintains consistent styling with placeholder content', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    // Check for consistent styling elements
    expect(screen.getByText(/This placeholder maintains consistent styling/)).toBeInTheDocument();
    
    // Check that the component has the expected tab-content class
    const tabContent = document.querySelector('.tab-content');
    expect(tabContent).toBeInTheDocument();
  });

  it('displays available functionality section', () => {
    renderWithWrapper(<OrchestrateTab />);
    
    expect(screen.getByText('Available Now')).toBeInTheDocument();
    expect(screen.getByText(/While orchestration features are being developed/)).toBeInTheDocument();
  });
});