// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Box,
  Button,
  CodeEditor } from
'@cloudscape-design/components';

import { useApp } from '../../contexts/AppContext';
import { useSession } from '../../contexts/SessionContext';
import { checkNetworkConnectivity } from '../../utils/errorHandling';

import { useTranslation } from 'react-i18next';
const LogsTab: React.FC = () => {
  const { t } = useTranslation();
  const { config, user, addNotification } = useApp();
  const { sessionState, clearChatHistory, generateNewSession } = useSession();

  const systemInfo = {
    sessionId: sessionState.sessionId,
    chatMessageCount: sessionState.chatHistory.length,
    lastActivity: sessionState.lastActivity.toISOString(),
    currentJob: sessionState.currentJob || 'None',
    networkStatus: checkNetworkConnectivity() ? 'Online' : 'Offline',
    user: {
      username: user?.username || 'Unknown',
      userId: user?.userId || 'Unknown'
    },
    configuration: {
      apiBaseUrl: config?.apiBaseUrl || 'Not configured',
      awsRegion: config?.awsConfig?.region || 'Not configured',
      documentBucket: config?.awsConfig?.documentBucket || 'Not configured'
    },
    browser: {
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      cookieEnabled: navigator.cookieEnabled
    }
  };

  const handleNewSession = () => {
    try {
      const newSessionId = generateNewSession();
      console.log('Generated new session:', newSessionId);

      addNotification({
        type: 'success',
        header: 'New Session Created',
        content: `Successfully created new session: ${newSessionId}`,
        dismissible: true
      });
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Session Creation Failed',
        content: error instanceof Error ? error.message : 'Failed to create new session',
        dismissible: true
      });
    }
  };

  const handleClearHistory = () => {
    try {
      clearChatHistory();
      addNotification({
        type: 'success',
        header: 'Chat History Cleared',
        content: 'Successfully cleared all chat messages from the current session.',
        dismissible: true
      });
    } catch (error) {
      addNotification({
        type: 'error',
        header: 'Clear History Failed',
        content: error instanceof Error ? error.message : 'Failed to clear chat history',
        dismissible: true
      });
    }
  };

  return (
    <div className="tab-content">
      <SpaceBetween direction="vertical" size="l">
        <Container
          header={
            <Header variant="h2" description="Current session information and system status">
              {t('logs.logs-tab.system-information')}
            </Header>
          }
        >

          <SpaceBetween direction="vertical" size="m">
            <Box>{t("logs.session.session_id")}
              <strong>{t("logs.session.session_id")}</strong> {sessionState.sessionId}
            </Box>
            <Box>{t("logs.session.user")}
              <strong>{t("logs.session.user")}</strong> {user?.username || 'Unknown'}
            </Box>
            <Box>{t("logs.session.last_activity")}
              <strong>{t("logs.session.last_activity")}</strong> {sessionState.lastActivity.toLocaleString()}
            </Box>
            <Box>{t("logs.session.current_job")}
              <strong>{t("logs.session.current_job")}</strong> {sessionState.currentJob || 'None'}
            </Box>
          </SpaceBetween>
        </Container>

        <Container
          header={
            <Header
              variant="h2"
              description={t("logs.history.description")}
              actions={
            <SpaceBetween direction="horizontal" size="s">
                  <Button
                variant="normal"
                onClick={handleClearHistory}
                disabled={sessionState.chatHistory.length === 0}>{t("logs.history.clear_history")}


              </Button>{t("logs.history.new_session")}
              <Button variant="primary" onClick={handleNewSession}>{t("logs.history.new_session")}

              </Button>
                </SpaceBetween>
            }>{t("logs.history.title")}


          </Header>
          }>

          <SpaceBetween direction="vertical" size="s">
            <Box>{t("logs.history.messages_count")}
              <strong>{t("logs.history.messages_count")}</strong> {sessionState.chatHistory.length}
            </Box>
            {sessionState.chatHistory.length > 0 &&
            <Box color="text-status-inactive">
                {t('logs.logs-tab.first-message')} {sessionState.chatHistory[0]?.timestamp.toLocaleString()}
              </Box>
            }
            {sessionState.chatHistory.length > 1 &&
            <Box color="text-status-inactive">
                {t('logs.logs-tab.latest-message')} {sessionState.chatHistory[sessionState.chatHistory.length - 1]?.timestamp.toLocaleString()}
              </Box>
            }
          </SpaceBetween>
        </Container>

        <Container
          header={
            <Header variant="h2" description="Application configuration and environment details">
              {t('logs.logs-tab.configuration-details')}
            </Header>
          }
        >

          <CodeEditor
            ace={undefined}
            language="json"
            value={JSON.stringify(systemInfo, null, 2)}
            readOnly
            preferences={{
              fontSize: 12,
              tabSize: 2
            }}
            loading={false}
            i18nStrings={{
              loadingState: 'Loading configuration...',
              errorState: 'Error loading configuration',
              errorStateRecovery: 'Retry'
            }} />

        </Container>
      </SpaceBetween>
    </div>);

};

export default LogsTab;