// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Authenticator } from '@aws-amplify/ui-react';

import StatusTab from '../StatusTab';
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

describe('StatusTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the job status interface', () => {
    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    expect(screen.getByText('Job Status')).toBeInTheDocument();
    expect(screen.getByText('Monitor document processing jobs and view detailed status')).toBeInTheDocument();
  });

  it('displays the job table with correct columns', () => {
    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    expect(screen.getByText('Job ID')).toBeInTheDocument();
    expect(screen.getByText('Document')).toBeInTheDocument();
    expect(screen.getByText('Sender')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Created')).toBeInTheDocument();
  });

  it('has a refresh button', () => {
    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    expect(refreshButton).toBeInTheDocument();
  });

  it('displays empty state when no jobs exist', async () => {
    // Mock empty response
    mockApiClient.getJobs.mockResolvedValue({
      jobs: [],
      total_count: 0,
      has_more: false,
    });

    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('No jobs found')).toBeInTheDocument();
      expect(screen.getByText('No processing jobs are currently available.')).toBeInTheDocument();
    });
  });

  it('displays mock data when API fails', async () => {
    // Mock API failure
    mockApiClient.getJobs.mockRejectedValue(new Error('API Error'));

    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('mock-job-001')).toBeInTheDocument();
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
  });

  it('handles refresh button click', async () => {
    mockApiClient.getJobs.mockResolvedValue({
      jobs: [],
      total_count: 0,
      has_more: false,
    });

    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(mockApiClient.getJobs).toHaveBeenCalledWith(10);
    });
  });

  it('opens job details modal when job is clicked', async () => {
    const mockJobs = [
      {
        job_id: 'test-job-001',
        s3_uri: 's3://test/document.pdf',
        status: 'completed',
        current_step: 'extraction_complete',
        created_at: Date.now(),
        updated_at: Date.now(),
        sender_name: 'Test Corp',
        doc_type: 'invoice',
      },
    ];

    const mockActions = [
      {
        job_id: 'test-job-001',
        started_at: new Date().toISOString(),
        agent: 'analyzer_agent',
        action_type: 'document_analysis',
        status: 'completed',
        completed_at: new Date().toISOString(),
      },
    ];

    mockApiClient.getJobs.mockResolvedValue({
      jobs: mockJobs,
      total_count: 1,
      has_more: false,
    });

    mockApiClient.getJobActions.mockResolvedValue({
      job_id: 'test-job-001',
      actions: mockActions,
      job_details: mockJobs[0],
    });

    render(
      <TestWrapper>
        <StatusTab />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('test-job-001')).toBeInTheDocument();
    });

    // Click on the job row
    const jobRow = screen.getByText('test-job-001').closest('tr');
    fireEvent.click(jobRow!);

    await waitFor(() => {
      expect(screen.getByText('Job Details')).toBeInTheDocument();
      expect(screen.getByText('Job Information')).toBeInTheDocument();
      expect(screen.getByText('Processing Actions')).toBeInTheDocument();
    });
  });
});