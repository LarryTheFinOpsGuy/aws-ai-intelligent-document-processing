import React, { useState, useEffect } from 'react';
import { Modal, Box, Container, Header, SpaceBetween, Button, Alert, Spinner, Table } from '@cloudscape-design/components';
import { getApiClient } from '../../services/apiClient';
import FlowDiagram from './FlowDiagram';
import ActionDetails from './ActionDetails';
import JobChatPanel from './JobChatPanel';
import { useTranslation } from 'react-i18next';
import './JobFlowViewer.css';

interface JobFlowViewerProps {
  jobId: string;
  visible: boolean;
  onDismiss: () => void;
}

interface JobAction {
  job_id: string;
  started_at: string;
  completed_at?: string;
  agent: string;
  result: string;
  success: boolean;
}

interface Job {
  job_id: string;
  status: string;
  doc_type?: string;
  sender_name?: string;
  s3_uri?: string;
  created_at: string;
  updated_at: string;
}

const JobFlowViewer: React.FC<JobFlowViewerProps> = ({ jobId, visible, onDismiss }) => {
  const { t } = useTranslation();
  const [job, setJob] = useState<Job | null>(null);
  const [actions, setActions] = useState<JobAction[]>([]);
  const [selectedAction, setSelectedAction] = useState<JobAction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [documentContent, setDocumentContent] = useState<string | null>(null);
  const [documentType, setDocumentType] = useState<string | null>(null);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [processingRule, setProcessingRule] = useState<any>(null);
  const [chatVisible, setChatVisible] = useState(false);

  const openInstructionsEditor = (instructionsUri: string, senderName: string) => {
    // Extract S3 key from full URI (remove s3://bucket-name/ prefix)
    const s3Key = instructionsUri.split('/').slice(3).join('/');
    const url = `/instructions-editor?key=${encodeURIComponent(s3Key)}&sender=${encodeURIComponent(senderName)}`;
    window.open(url, '_blank', 'width=1200,height=800');
  };

  const toggleRuleStatus = async (documentId: string, currentStatus: string) => {
    try {
      const apiClient = getApiClient();
      const newStatus = currentStatus === 'ACTIVE' ? 'PENDING REVIEW' : 'ACTIVE';

      await apiClient.updateProcessingRule(documentId, { status: newStatus });

      // Refresh the processing rule data
      if (processingRule && processingRule.document_id === documentId) {
        setProcessingRule({ ...processingRule, status: newStatus });
      }
    } catch (error) {
      console.error('Failed to toggle rule status:', error);
    }
  };

  const fetchJobFlow = async () => {
    if (!visible || !jobId) return;

    setLoading(true);
    setError(null);

    try {
      const apiClient = getApiClient();
      const response = await apiClient.getJobFlow(jobId);
      setJob(response.job);
      setActions(response.actions);

      // Auto-select first failed action
      if (!selectedAction) {
        const failedAction = response.actions.find((a) => !a.success);
        if (failedAction) setSelectedAction(failedAction);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load job flow');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible && jobId) {
      fetchJobFlow();
    }
  }, [visible, jobId]);

  useEffect(() => {
    if (!autoRefresh || !visible) return;

    const interval = setInterval(fetchJobFlow, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, visible]);

  useEffect(() => {
    if (job && ['COMPLETED', 'FAILED'].includes(job.status)) {
      setAutoRefresh(false);
    }
  }, [job]);

  const formatDuration = (startDate?: string, stopDate?: string) => {
    if (!startDate) return 'N/A';
    const start = new Date(startDate);
    const end = stopDate ? new Date(stopDate) : new Date();
    const duration = Math.floor((end.getTime() - start.getTime()) / 1000);
    const minutes = Math.floor(duration / 60);
    const seconds = duration % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const loadDocumentContent = async (type: string) => {
    if (!job?.s3_uri) return;

    setDocumentLoading(true);
    setDocumentContent(null);
    setDocumentType(type);

    try {
      const apiClient = getApiClient();

      if (type === 'processing-rules') {
        // Get processing rule from vector DB by document ID
        const docId = job.match_doc_id || job.job_id;
        const response = await apiClient.getProcessingRuleByDocId(docId);
        setProcessingRule(response);
        setDocumentContent(null);
        setPdfUrl(null);
      } else {
        // Get document content from S3 using the correct URI from the job record
        let s3Key = '';

        if (type === 'original') {
          s3Key = job.s3_uri.split('/').slice(3).join('/');
        } else if (type === 'extracted-text') {
          if (job.markdown_s3_uri) {
            s3Key = job.markdown_s3_uri.split('/').slice(3).join('/');
          } else {
            throw new Error('Extracted text not available for this document');
          }
        } else if (type === 'extracted-data') {
          if (job.extracted_data_s3_uri) {
            s3Key = job.extracted_data_s3_uri.split('/').slice(3).join('/');
          } else {
            throw new Error('Extracted data not available for this document');
          }
        }

        const response = await apiClient.getDocumentContent(s3Key);

        // Handle PDF files differently
        if (type === 'original' && job.s3_uri.toLowerCase().endsWith('.pdf')) {
          // Create blob URL for PDF display
          const binaryString = atob(response.content);
          const bytes = new Uint8Array(binaryString.length);
          for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
          }
          const blob = new Blob([bytes], { type: 'application/pdf' });
          const url = URL.createObjectURL(blob);
          setPdfUrl(url);
          setDocumentContent(null);
        } else {
          setPdfUrl(null);
          setDocumentContent(response.content);
        }
      }
    } catch (err: any) {
      setDocumentContent(`Error loading ${type}: ${err.message}`);
    } finally {
      setDocumentLoading(false);
    }
  };

  const clearDocumentView = () => {
    setDocumentContent(null);
    setDocumentType(null);
    setProcessingRule(null);
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
      setPdfUrl(null);
    }
  };

  if (loading && !job) {
    return (
      <Modal visible={visible} onDismiss={onDismiss} header={t("ui.job-flow-viewer.title")} size="max">
        <Box textAlign="center" padding="xxl">
          <Spinner size="large" />{t("ui.job-flow-viewer.loading")}
          <Box variant="p" margin={{ top: 'm' }}>{t("ui.job-flow-viewer.loading")}</Box>
        </Box>
      </Modal>);

  }

  if (error) {
    return (
      <Modal visible={visible} onDismiss={onDismiss} header={t("ui.job-flow-viewer.processing-flow-1")} size={t("ui.job-flow-viewer.error-loading")}>
        <Alert type={t("ui.job-flow-viewer.error-loading")} header="Error loading job flow">{error}</Alert>
      </Modal>);

  }

  if (!job) {
    return (
      <Modal visible={visible} onDismiss={onDismiss} header={t("ui.job-flow-viewer.processing-flow-2")} size="max">{t("ui.job-flow-viewer.no-data-available")}
        <Alert type="info">{t("ui.job-flow-viewer.no-data-available")}</Alert>
      </Modal>);

  }

  return (
    <>
    <Modal
        visible={visible}
        onDismiss={onDismiss}
        header={
        <Header
          variant="h2"
          actions={
          <SpaceBetween direction="horizontal" size="xs">
              <Button
              variant="normal"
              onClick={() => setChatVisible(true)}
              iconName="contact">{t("ui.job-flow-viewer.chat-about-job")}


            </Button>
              <Button
              variant={autoRefresh ? 'primary' : 'normal'}
              onClick={() => setAutoRefresh(!autoRefresh)}
              iconName={autoRefresh ? 'status-positive' : 'status-stopped'}>

                {autoRefresh ? 'Auto-Refresh On' : 'Auto-Refresh Off'}
              </Button>
              <Button onClick={fetchJobFlow} iconName="refresh" loading={loading}>
                {t('ui.job-flow-viewer.refresh')}
              </Button>
            </SpaceBetween>
          }>
            {t("ui.job-flow-viewer.title")}
          </Header>
        }
        size="max">

      <SpaceBetween size="l">{t("ui.job-flow-viewer.overview-title")}
          <Container header={<Header variant="h3">{t("ui.job-flow-viewer.overview-title")}</Header>}>
          <SpaceBetween size="m">
            <SpaceBetween direction="horizontal" size="l">
              <Box>
                <Box variant="awsui-key-label">{t("ui.job-flow-viewer.job-id")}</Box>
                <Box variant="code">{job.job_id}</Box>
              </Box>
              <Box>
                <Box variant="awsui-key-label">{t('ui.job-flow-viewer.status')}</Box>
                <Box className={`job-status job-status-${job.status.toLowerCase()}`}>{job.status}</Box>
              </Box>
              <Box>
                <Box variant="awsui-key-label">{t('ui.job-flow-viewer.duration')}</Box>
                <Box>{formatDuration(job.created_at, job.updated_at)}</Box>
              </Box>
              <Box>
                <Box variant="awsui-key-label">{t('ui.job-flow-viewer.created')}</Box>
                <Box>{new Date(job.created_at).toLocaleString()}</Box>
              </Box>
              {job.doc_type &&
                <Box>
                  <Box variant="awsui-key-label">{t('ui.job-flow-viewer.document-type')}</Box>
                  <Box>{job.doc_type}</Box>
                </Box>
                }
            </SpaceBetween>
            
            <SpaceBetween direction="horizontal" size="s">
              <Button
                  variant="link"
                  onClick={() => loadDocumentContent('original')}
                  loading={documentLoading && documentType === 'original'}
                  disabled={!job?.s3_uri}>{t("ui.actions.view_original_document")}


                </Button>
              <Button
                  variant="link"
                  onClick={() => loadDocumentContent('extracted-text')}
                  loading={documentLoading && documentType === 'extracted-text'}
                  disabled={!job?.markdown_s3_uri}>{t("ui.actions.view_extracted_text")}


                </Button>
              <Button
                  variant="link"
                  onClick={() => loadDocumentContent('extracted-data')}
                  loading={documentLoading && documentType === 'extracted-data'}
                  disabled={!job?.extracted_data_s3_uri}>{t("ui.actions.view_extracted_data")}


                </Button>
              <Button
                  variant="link"
                  onClick={() => loadDocumentContent('processing-rules')}
                  loading={documentLoading && documentType === 'processing-rules'}
                  disabled={!job?.match_doc_id}>{t("ui.actions.view_processing_rules")}


                </Button>
              {(documentContent || pdfUrl || processingRule) &&
                <Button variant="link" onClick={clearDocumentView}>
                  {t('ui.job-flow-viewer.clear-view')}
                </Button>
                }
            </SpaceBetween>
          </SpaceBetween>
        </Container>

        {(documentContent || pdfUrl || processingRule) &&
          <Container
            header={
            <Header variant="h3">
                {documentType === 'original' && 'Original Document'}
                {documentType === 'extracted-text' && 'Extracted Text'}
                {documentType === 'extracted-data' && 'Extracted Data'}
                {documentType === 'processing-rules' && 'Processing Rules'}
              </Header>
            }>

            <Box>
              {processingRule ?
              processingRule.error ?
              <Alert type="warning">
                    {processingRule.error}
                  </Alert> :

              <Table
                columnDefinitions={[
                { id: 'sender', header: 'Sender', cell: (item: any) => item.sender_name },
                { id: 'type', header: 'Document Type', cell: (item: any) => item.document_type },
                { id: 'address', header: 'Address', cell: (item: any) => item.sender_address },
                { id: 'status', header: 'Status', cell: (item: any) =>
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    backgroundColor: item.status === 'ACTIVE' ? '#d4edda' :
                    item.status === 'PENDING REVIEW' ? '#fff3cd' : '#f8d7da',
                    color: item.status === 'ACTIVE' ? '#155724' :
                    item.status === 'PENDING REVIEW' ? '#856404' : '#721c24'
                  }}>
                          {item.status}
                        </span>
                },
                { id: 'instructions', header: 'Instructions', cell: (item: any) =>
                  <Button
                    variant="link"
                    onClick={() => openInstructionsEditor(item.instructions_s3_uri, item.sender_name)}
                    disabled={!item.instructions_s3_uri}>

                          {t('ui.job-flow-viewer.view-edit-instructions')}
                        </Button>
                },
                { id: 'actions', header: 'Actions', cell: (item: any) =>
                  <Button
                    variant="link"
                    onClick={() => toggleRuleStatus(item.document_id, item.status)}
                    disabled={item.status === 'ARCHIVED'}>

                          {item.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
                        </Button>
                }]
                }
                items={[processingRule]}
                empty="No processing rule found" /> :


              pdfUrl ?
              <iframe
                src={pdfUrl}
                width="100%"
                height="600px"
                style={{ border: '1px solid #e1e4e8', borderRadius: '4px' }}
                title="PDF Document" /> :


              <pre style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: '400px',
                overflow: 'auto',
                padding: '12px',
                backgroundColor: '#f8f9fa',
                border: '1px solid #e1e4e8',
                borderRadius: '4px',
                fontSize: '12px',
                fontFamily: 'Monaco, Consolas, "Courier New", monospace'
              }}>
                  {documentContent}
                </pre>
              }
            </Box>
          </Container>
          }

        <Container header={<Header variant="h3">{t("ui.job-flow-viewer.processing")}</Header>}>
          <FlowDiagram
              actions={actions}
              selectedAction={selectedAction}
              onActionClick={setSelectedAction} />

        </Container>

        <Container header={<Header variant="h3">{t("ui.actions.details")}</Header>}>
          <ActionDetails action={selectedAction} formatDuration={formatDuration} />
        </Container>
      </SpaceBetween>
    </Modal>

    {chatVisible &&
      <JobChatPanel
        visible={chatVisible}
        onDismiss={() => setChatVisible(false)}
        jobId={jobId} />

      }
    </>);

};

export default JobFlowViewer;
