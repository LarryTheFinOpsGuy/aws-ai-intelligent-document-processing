// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState } from 'react';
import {
  Container,
  Header,
  Box,
  SpaceBetween,
  Button,
  FileUpload,
  ProgressBar,
  Link,
  Table } from
'@cloudscape-design/components';
import { useApp } from '../../contexts/AppContext';
import { useSession } from '../../contexts/SessionContext';
import { uploadToS3WithPresignedUrl } from '../../utils/s3UploadPresigned';
import JobFlowViewer from '../JobFlowViewer';

import { useTranslation } from 'react-i18next';
const OrchestrateTab: React.FC = () => {
  const { t } = useTranslation();
  const { addNotification, apiClient } = useApp();
  const { assumeSession } = useSession();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadHistory, setUploadHistory] = useState<Array<{
    jobId: string;
    fileName: string;
    uploadTime: string;
  }>>(() => {
    const saved = localStorage.getItem('uploadHistory');
    return saved ? JSON.parse(saved) : [];
  });
  const [flowModalVisible, setFlowModalVisible] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const handleFileChange = ({ detail }: any) => {
    const files = detail.value;
    if (files.length > 0) {
      const file = files[0];
      if (file.type === 'application/pdf') {
        setSelectedFile(file);
      } else {
        addNotification({
          type: 'error',
          header: 'Invalid File Type',
          content: 'Please select a PDF file.',
          dismissible: true
        });
        setSelectedFile(null);
      }
    } else {
      setSelectedFile(null);
    }
  };

  const handleUploadAndProcess = async () => {
    if (!selectedFile || !apiClient) {
      console.error('❌ Missing required dependencies:', {
        hasFile: !!selectedFile,
        hasApiClient: !!apiClient
      });
      return;
    }

    console.log('🚀 Starting upload and process flow');
    setUploading(true);
    setUploadProgress(0);

    try {
      addNotification({
        type: 'info',
        header: 'Upload Started',
        content: `Uploading ${selectedFile.name}...`,
        dismissible: true
      });

      console.log('📤 Calling uploadToS3WithPresignedUrl...');
      const s3Uri = await uploadToS3WithPresignedUrl(selectedFile, apiClient);
      console.log('✅ Upload complete, S3 URI:', s3Uri);

      setUploadProgress(100);

      addNotification({
        type: 'success',
        header: 'Upload Complete',
        content: `File uploaded successfully: ${s3Uri}`,
        dismissible: true
      });

      addNotification({
        type: 'info',
        header: 'Creating Job',
        content: 'Initiating document processing...',
        dismissible: true
      });

      console.log('🔨 Calling createJob API...');
      const jobResponse = await apiClient.createJob(s3Uri);
      console.log('✅ Job created:', jobResponse);

      // Add to upload history
      const newUpload = {
        jobId: jobResponse.job_record.job_id,
        fileName: selectedFile.name,
        uploadTime: new Date().toLocaleString()
      };

      const updatedHistory = [newUpload, ...uploadHistory].slice(0, 10);
      setUploadHistory(updatedHistory);
      localStorage.setItem('uploadHistory', JSON.stringify(updatedHistory));

      assumeSession(jobResponse.session_id);
      console.log('🔄 Session updated to:', jobResponse.session_id);

      addNotification({
        type: 'success',
        header: 'Job Created',
        content: `Processing started. Job ID: ${jobResponse.job_record.job_id}`,
        dismissible: true
      });

      // Clear the file selector for next upload
      setSelectedFile(null);

    } catch (error) {
      console.error('💥 Error in upload and process:', error);
      addNotification({
        type: 'error',
        header: 'Processing Failed',
        content: error instanceof Error ? error.message : 'Failed to process document',
        dismissible: true
      });
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div className="tab-content">
      <Container
        header={
          <Header 
            variant="h2" 
            description={t("orchestrate.upload.description")}
          >
            {t("orchestrate.upload.title")}
          </Header>
        }
      >

        <SpaceBetween direction="vertical" size="l">
          <Container
            header={
            <Header variant="h3">{t("orchestrate.upload.document_title")}

            </Header>
            }>

            <SpaceBetween direction="vertical" size="m">
              <FileUpload
                onChange={handleFileChange}
                value={selectedFile ? [selectedFile] : []}
                i18nStrings={{
                  uploadButtonText: (e) => e ? "Choose files" : "Choose file",
                  dropzoneText: (e) => e ? "Drop files to upload" : "Drop file to upload",
                  removeFileAriaLabel: (e) => `Remove file ${e + 1}`,
                  limitShowFewer: "Show fewer files",
                  limitShowMore: "Show more files",
                  errorIconAriaLabel: "Error"
                }}
                showFileLastModified
                showFileSize
                showFileThumbnail
                tokenLimit={3}
                constraintText="PDF files only"
                accept=".pdf,application/pdf" />

              
              {uploading &&
              <ProgressBar
                value={uploadProgress}
                label="Upload progress"
                description={`Uploading ${selectedFile?.name}`} />

              }
              
              <Button
                variant="primary"
                onClick={handleUploadAndProcess}
                disabled={!selectedFile || uploading}
                loading={uploading}>{t("orchestrate.upload.button")}


              </Button>
            </SpaceBetween>
          </Container>

          <Container
            header={
            <Header variant="h3">{t("orchestrate.upload.history_title")}

            </Header>
            }>

            {uploadHistory.length > 0 ?
            <Table
              columnDefinitions={[
              {
                id: 'jobId',
                header: 'Job ID',
                cell: (item) =>
                <Link
                  variant="primary"
                  onFollow={(e) => {
                    e.preventDefault();
                    setSelectedJobId(item.jobId);
                    setFlowModalVisible(true);
                  }}>

                        {item.jobId}
                      </Link>

              },
              {
                id: 'fileName',
                header: 'File Name',
                cell: (item) => item.fileName
              },
              {
                id: 'uploadTime',
                header: 'Upload Time',
                cell: (item) => item.uploadTime
              }]
              }
              items={uploadHistory}
              variant="embedded"
              empty={
              <Box textAlign="center" color="inherit">
                    <Box variant="p">{t('orchestrate.orchestrate-tab.no-uploads-yet')}</Box>
                  </Box>
              } /> :


            <Box variant="p" color="text-status-inactive">
                {t('orchestrate.orchestrate-tab.no-upload-history')}
              </Box>
            }
          </Container>
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

export default OrchestrateTab;