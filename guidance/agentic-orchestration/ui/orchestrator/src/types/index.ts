// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

// Core application types

export interface ProcessingJob {
  job_id: string;
  s3_uri: string;
  status: 'started' | 'processing' | 'completed' | 'failed';
  current_step: string;
  created_at: number;
  updated_at: number;
  sender_name?: string;
  doc_type?: string;
}

export interface ProcessingAction {
  job_id: string;
  started_at: string;
  agent: string;
  action_type: string;
  status: 'running' | 'completed' | 'failed';
  result?: any;
  error_message?: string;
  completed_at?: string;
}

export interface JobListResponse {
  jobs: ProcessingJob[];
  total_count: number;
  has_more: boolean;
  status_counts: {
    CREATED: number;
    PROCESSING: number;
    COMPLETED: number;
    FAILED: number;
  };
}

export interface JobActionsResponse {
  job_id: string;
  actions: ProcessingAction[];
  job_details: ProcessingJob;
}

export interface JobAction {
  job_id: string;
  started_at: string;
  completed_at?: string;
  agent: string;
  result: string;
  success: boolean;
}

export interface JobFlowResponse {
  job: ProcessingJob;
  actions: JobAction[];
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface SessionState {
  sessionId: string;
  chatHistory: ChatMessage[];
  currentJob?: string;
  lastActivity: Date;
}

export interface AppConfiguration {
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

export interface ErrorNotification {
  type: 'error' | 'warning' | 'info' | 'success';
  title: string;
  message: string;
  dismissible: boolean;
  action?: {
    label: string;
    handler: () => void;
  };
}

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface ChatResponse {
  message: string;
  sessionId: string;
  timestamp: string;
}

export interface CreateJobResponse {
  session_id: string;
  document_uri: string;
  message: string;
  job_record: ProcessingJob;
}

export interface AuthUser {
  username: string;
  email?: string;
  attributes?: Record<string, any>;
}

export interface SessionManager {
  sessionId: string;
  generateNewSession(): string;
  assumeSession(sessionId: string): void;
  clearSession(): void;
}

export interface ApiClientConfig {
  baseURL: string;
  timeout?: number;
}

export interface ApiClientOptions extends ApiClientConfig {
  enableRequestLogging?: boolean;
  enableResponseLogging?: boolean;
  defaultRetryOptions?: {
    maxAttempts?: number;
    baseDelay?: number;
    maxDelay?: number;
    backoffFactor?: number;
  };
}