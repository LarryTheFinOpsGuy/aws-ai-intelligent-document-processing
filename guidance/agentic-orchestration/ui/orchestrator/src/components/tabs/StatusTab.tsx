// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from 'react';
import {
  Container,
  Header,
  Table,
  Button,
  SpaceBetween,
  Box,
  StatusIndicator,
  Input,
  Select,
  Link } from
'@cloudscape-design/components';
import { getApiClient } from '../../services/apiClient';
import { useApp } from '../../contexts/AppContext';
import { processError } from '../../utils/errorHandling';
import JobFlowViewer from '../JobFlowViewer';

import { useTranslation } from 'react-i18next';
interface ProcessingJob {
  job_id: string;
  s3_uri: string;
  status: 'started' | 'processing' | 'completed' | 'failed';
  current_step: string;
  created_at: number;
  updated_at: number;
  sender_name?: string;
  doc_type?: string;
}

const StatusTab: React.FC = () => {
  const { t } = useTranslation();
  const { addNotification } = useApp();
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [flowModalVisible, setFlowModalVisible] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState('COMPLETED');
  const [statusCounts, setStatusCounts] = useState<{[key: string]: number;}>({});

  const loadJobs = async (status: string = selectedStatus) => {
    setLoading(true);
    try {
      const apiClient = getApiClient();
      const response = await apiClient.getJobs(10, status);
      setJobs(response.jobs);
      setStatusCounts(response.status_counts);
    } catch (error) {
      console.error('Failed to load jobs:', error);
      const errorDetails = processError(error);

      addNotification({
        type: 'error',
        header: errorDetails.title,
        content: errorDetails.message,
        dismissible: true,
        action: errorDetails.retryable ? {
          buttonText: 'Retry',
          onButtonClick: () => loadJobs(status)
        } : undefined
      });

      // Fallback to mock data for development
      const mockJobs: ProcessingJob[] = [
      {
        job_id: 'mock-job-001',
        s3_uri: 's3://documents/invoice-001.pdf',
        status: 'completed',
        current_step: 'extraction_complete',
        created_at: Date.now() - 3600000,
        updated_at: Date.now() - 1800000,
        sender_name: 'Acme Corp',
        doc_type: 'invoice'
      },
      {
        job_id: 'mock-job-002',
        s3_uri: 's3://documents/po-002.pdf',
        status: 'processing',
        current_step: 'data_extraction',
        created_at: Date.now() - 1800000,
        updated_at: Date.now() - 300000,
        sender_name: 'Beta Industries',
        doc_type: 'purchase_order'
      }];

      setJobs(mockJobs);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  const handleJobClick = async (job: ProcessingJob) => {
    setSelectedJobId(job.job_id);
    setFlowModalVisible(true);
  };

  const getStatusIndicator = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return <StatusIndicator type="success">{t('status.status-tab.completed')}</StatusIndicator>;
      case 'PROCESSING':
        return <StatusIndicator type="in-progress">{t('status.status-tab.processing')}</StatusIndicator>;
      case 'FAILED':
        return <StatusIndicator type="error">{t('status.status-tab.failed')}</StatusIndicator>;
      case 'CREATED':
        return <StatusIndicator type="pending">{t('status.status-tab.created')}</StatusIndicator>;
      default:
        return <StatusIndicator type="pending">{status}</StatusIndicator>;
    }
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadJobs(selectedStatus);
      return;
    }

    setSearching(true);
    try {
      const apiClient = getApiClient();
      const response = await apiClient.searchJob(searchQuery.trim());
      setJobs([response.job]);
    } catch (error) {
      console.error('Failed to search job:', error);
      const errorDetails = processError(error);

      addNotification({
        type: 'error',
        header: 'Job Not Found',
        content: errorDetails.message,
        dismissible: true
      });

      setJobs([]);
    } finally {
      setSearching(false);
    }
  };

  const filteredJobs = jobs.filter((job) =>
  job.job_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="tab-content">
      <Container
        header={
          <Header
            variant="h2"
            description={t("status.status-tab.description")}
            actions={
          <Button
            iconName="refresh"
            onClick={() => loadJobs(selectedStatus)}
            loading={loading}>

                {t('status.status-tab.refresh')}
              </Button>
          }>{t("status.status-tab.title")}


        </Header>
        }>

        <SpaceBetween size="m">
          <SpaceBetween direction="horizontal" size="xs">
            <Select
              selectedOption={{
                label: `${selectedStatus} (${statusCounts[selectedStatus] || 0})`,
                value: selectedStatus
              }}
              onChange={({ detail }) => {
                const newStatus = detail.selectedOption.value;
                setSelectedStatus(newStatus);
                loadJobs(newStatus);
              }}
              options={[
              { label: `COMPLETED (${statusCounts.COMPLETED || 0})`, value: 'COMPLETED' },
              { label: `PROCESSING (${statusCounts.PROCESSING || 0})`, value: 'PROCESSING' },
              { label: `CREATED (${statusCounts.CREATED || 0})`, value: 'CREATED' },
              { label: `FAILED (${statusCounts.FAILED || 0})`, value: 'FAILED' }]
              }
              placeholder={t("status.status-tab.select-status")} />

            <Input
              type={t("status.jobs.search_placeholder")}
              placeholder={t("status.jobs.search_placeholder")}
              value={searchQuery}
              onChange={({ detail }) => setSearchQuery(detail.value)}
              onKeyDown={(e) => {
                if (e.detail.key === 'Enter') {
                  handleSearch();
                }
              }}
              clearAriaLabel="Clear search" />

            <Button
              onClick={handleSearch}
              loading={searching}
              iconName="search">

              {t('status.status-tab.search')}
            </Button>
            {searchQuery &&
            <Button
              onClick={() => {
                setSearchQuery('');
                loadJobs(selectedStatus);
              }}
              iconName="close">

                {t('status.status-tab.clear')}
              </Button>
            }
          </SpaceBetween>
          <Table
            columnDefinitions={[
            {
              id: 'job_id',
              header: 'Job ID',
              cell: (item: ProcessingJob) =>
              <Link
                variant="primary"
                onFollow={(e) => {
                  e.preventDefault();
                  setSelectedJobId(item.job_id);
                  setFlowModalVisible(true);
                }}>

                  {item.job_id}
                </Link>,

              sortingField: 'job_id',
              width: 320
            },
            {
              id: 'sender_name',
              header: 'Sender',
              cell: (item: ProcessingJob) => item.sender_name || '-'
            },
            {
              id: 'status',
              header: 'Status',
              cell: (item: ProcessingJob) => getStatusIndicator(item.status)
            },
            {
              id: 'created_at',
              header: 'Created',
              cell: (item: ProcessingJob) => formatTimestamp(item.created_at),
              sortingField: 'created_at'
            },
            {
              id: 's3_uri',
              header: 'Document',
              cell: (item: ProcessingJob) => item.s3_uri
            }]
            }
            items={searchQuery ? jobs : filteredJobs}
            loading={loading || searching}
            loadingText={searching ? "Searching..." : "Loading jobs..."}
            onRowClick={({ detail }) => handleJobClick(detail.item)}
            empty={
            <Box textAlign="center" color="inherit">{t("status.jobs.no_jobs_found")}
              <b>{t("status.jobs.no_jobs_found")}</b>
              <Box variant="p" color="inherit">
                {searchQuery ? 'No job found with that ID.' : 'No processing jobs are currently available.'}
              </Box>
            </Box>
            }
            header={
            <Header counter={`(${searchQuery ? jobs.length : filteredJobs.length})`}>{t("status.status-tab.recent-jobs")}

            </Header>
            } />

        </SpaceBetween>
      </Container>

      {flowModalVisible && selectedJobId &&
      <JobFlowViewer
        jobId={selectedJobId}
        visible={flowModalVisible}
        onDismiss={() => {
          setFlowModalVisible(false);
          setSelectedJobId(null);
        }} />

      }
    </div>);

};

export default StatusTab;