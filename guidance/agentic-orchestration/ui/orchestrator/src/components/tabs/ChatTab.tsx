// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useRef, useEffect } from 'react';
import {
  Container,
  Header,
  Button,
  SpaceBetween,
  Box } from
'@cloudscape-design/components';

import { useSession } from '../../contexts/SessionContext';
import { useApp } from '../../contexts/AppContext';
import { validateChatMessage, processError } from '../../utils/errorHandling';
import ValidatedInput from '../common/ValidatedInput';
import LoadingIndicator from '../common/LoadingIndicator';

import { useTranslation } from 'react-i18next';
const ChatTab: React.FC = () => {
  const { t } = useTranslation();
  const { sessionState, addChatMessage, clearChatHistory } = useSession();
  const { apiClient, addNotification } = useApp();
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [sessionState.chatHistory]);

  const handleSendMessage = async () => {
    if (!message.trim() || loading || !apiClient) return;

    // Validate message before sending
    try {
      validateChatMessage(message);
      setValidationError('');
    } catch (error) {
      if (error instanceof Error) {
        setValidationError(error.message);
        return;
      }
    }

    const userMessage = message.trim();
    setMessage('');

    // Add user message to chat history
    addChatMessage({
      type: 'user',
      content: userMessage
    });

    setLoading(true);
    try {
      // Send message to AgentCore via API
      const response = await apiClient.sendChatMessage(userMessage);

      // Add agent response to chat history
      addChatMessage({
        type: 'assistant',
        content: response.message || response.response || 'No response received from agent.'
      });

      // Show success notification for successful message
      addNotification({
        type: 'success',
        header: 'Message Sent',
        content: 'Your message was sent successfully to the AI agent.',
        dismissible: true
      });
    } catch (error) {
      console.error('Failed to send message:', error);

      const errorDetails = processError(error);

      // Show error notification
      addNotification({
        type: 'error',
        header: errorDetails.title,
        content: errorDetails.message,
        dismissible: true,
        action: errorDetails.retryable ? {
          buttonText: 'Retry',
          onButtonClick: () => {
            setMessage(userMessage);
            handleSendMessage();
          }
        } : undefined
      });

      // Add error message to chat history for user visibility
      addChatMessage({
        type: 'assistant',
        content: `Sorry, I encountered an error: ${errorDetails.message}. ${errorDetails.userAction || 'Please try again.'}`
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.stopPropagation();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString();
  };

  return (
    <div className="tab-content">
      <Container
        header={
          <Header
            variant="h2"
            description={t("chat.interface.description")}
            actions={
          <Button
            variant="normal"
            onClick={() => {
              clearChatHistory();
              addNotification({
                type: 'success',
                header: 'Chat Cleared',
                content: 'Chat history has been cleared successfully.',
                dismissible: true
              });
            }}
            disabled={sessionState.chatHistory.length === 0}>{t("chat.actions.clear_history")}


          </Button>
          }>{t("chat.interface.title")}


        </Header>
        }>


        <SpaceBetween direction="vertical" size="s">
          <Box variant="small" color="text-status-inactive">
            {t("chat.session.session_id")} {sessionState.sessionId} {t("chat.session.messages")} {sessionState.chatHistory.length}
          </Box>
        </SpaceBetween>

        <div className="chat-container">
          <div className="chat-messages">
            {sessionState.chatHistory.length === 0 ?
            <Box textAlign="center" color="text-status-inactive">
                <Box variant="h3">{t('chat.chat-tab.welcome')}</Box>
                <Box variant="p">
                  {t('chat.chat-tab.start-conversation')}
                </Box>
                {!apiClient &&
              <Box variant="small" color="text-status-error">
                    {t('chat.chat-tab.api-not-available')}
                  </Box>
              }
              </Box> :

            <SpaceBetween direction="vertical" size="m">
                {sessionState.chatHistory.map((msg) =>
              <Box
                key={msg.id}
                padding="m"
                backgroundColor={msg.type === 'user' ? 'color-background-container-content' : 'color-background-layout-panel-content'}
                borderRadius="s">

                    <SpaceBetween direction="vertical" size="xs">
                      <Box fontSize="body-s" color="text-status-inactive">
                        <strong>{msg.type === 'user' ? 'You' : 'AI Agent'}</strong> • {formatTimestamp(msg.timestamp)}
                      </Box>
                      <Box>
                        <pre style={{
                      whiteSpace: 'pre-wrap',
                      wordWrap: 'break-word',
                      fontFamily: 'inherit',
                      margin: 0
                    }}>
                          {msg.content}
                        </pre>
                      </Box>
                    </SpaceBetween>
                  </Box>
              )}
                {loading &&
              <Box
                padding="s"
                backgroundColor="color-background-layout-panel-content"
                borderRadius="s">

                    <LoadingIndicator
                  size="normal"
                  message="Agent is typing..."
                  inline={true}
                  variant="spinner" />

                  </Box>
              }
              </SpaceBetween>
            }
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-container">
            <SpaceBetween direction="horizontal" size="s">
              <div style={{ flex: 1 }}>
                <ValidatedInput
                  value={message}
                  onChange={setMessage}
                  placeholder={loading ? "Agent is responding..." : "Type your message here..."}
                  disabled={loading || !apiClient}
                  validator={validateChatMessage}
                  validateOnBlur={false}
                  validateOnChange={true}
                  errorText={validationError}
                  onKeyDown={handleKeyDown} />

              </div>
              <Button
                variant="primary"
                onClick={handleSendMessage}
                disabled={!message.trim() || loading || !apiClient || !!validationError}
                loading={loading}>

                {t('chat.chat-tab.send')}
              </Button>
            </SpaceBetween>
          </div>
        </div>
      </Container>
    </div>);

};

export default ChatTab;