import React, { useState, useRef, useEffect } from 'react';
import {
  Modal,
  Button,
  SpaceBetween,
  Box,
} from '@cloudscape-design/components';
import { useTranslation } from 'react-i18next';
import { useApp } from '../../contexts/AppContext';
import { validateChatMessage, processError } from '../../utils/errorHandling';
import ValidatedInput from '../common/ValidatedInput';
import LoadingIndicator from '../common/LoadingIndicator';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface JobChatPanelProps {
  visible: boolean;
  onDismiss: () => void;
  jobId: string;
}

const JobChatPanel: React.FC<JobChatPanelProps> = ({ visible, onDismiss, jobId }) => {
  const { t } = useTranslation();
  const { apiClient, addNotification } = useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [initialMessageSent, setInitialMessageSent] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Send initial message when panel opens
  useEffect(() => {
    if (visible && !initialMessageSent && apiClient) {
      const initialMessage = `Analyze what happened with job ${jobId}`;
      sendMessage(initialMessage, true);
      setInitialMessageSent(true);
    }
  }, [visible, initialMessageSent, jobId, apiClient]);

  // Reset state when panel closes
  useEffect(() => {
    if (!visible) {
      setMessages([]);
      setInitialMessageSent(false);
      setMessage('');
      setValidationError('');
    }
  }, [visible]);

  const addMessage = (type: 'user' | 'assistant', content: string) => {
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      type,
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, newMessage]);
  };

  const sendMessage = async (messageText: string, isInitial = false) => {
    if (!messageText.trim() || loading || !apiClient) return;

    if (!isInitial) {
      try {
        validateChatMessage(messageText);
        setValidationError('');
      } catch (error) {
        if (error instanceof Error) {
          setValidationError(error.message);
          return;
        }
      }
    }

    const userMessage = messageText.trim();
    if (!isInitial) {
      setMessage('');
    }
    
    addMessage('user', userMessage);
    setLoading(true);

    try {
      const response = await apiClient.sendChatMessage(userMessage);
      addMessage('assistant', response.message || response.response || 'No response received from agent.');
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorDetails = processError(error);
      
      addNotification({
        type: 'error',
        header: 'Chat Error',
        content: errorDetails.message,
        dismissible: true,
      });
      
      addMessage('assistant', `Sorry, I encountered an error: ${errorDetails.message}. Please try again.`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = () => {
    sendMessage(message);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString();
  };

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header={`Chat about Job ${jobId}`}
      size="large"
    >
      <div style={{ height: '500px', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflowY: 'auto', marginBottom: '16px' }}>
          {messages.length === 0 && !loading ? (
            <Box textAlign="center" color="text-status-inactive">
              <Box variant="p">{t('ui.job-chat-panel.starting-analysis')} {jobId}...</Box>
            </Box>
          ) : (
            <SpaceBetween direction="vertical" size="m">
              {messages.map((msg) => (
                <Box
                  key={msg.id}
                  padding="m"
                  backgroundColor={msg.type === 'user' ? 'color-background-container-content' : 'color-background-layout-panel-content'}
                  borderRadius="s"
                >
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
              ))}
              {loading && (
                <Box
                  padding="s"
                  backgroundColor="color-background-layout-panel-content"
                  borderRadius="s"
                >
                  <LoadingIndicator 
                    size="normal" 
                    message="Agent is analyzing..." 
                    inline={true}
                    variant="spinner"
                  />
                </Box>
              )}
            </SpaceBetween>
          )}
          <div ref={messagesEndRef} />
        </div>

        <SpaceBetween direction="horizontal" size="s">
          <div style={{ flex: 1 }}>
            <ValidatedInput
              value={message}
              onChange={setMessage}
              placeholder={loading ? "Agent is responding..." : "Ask about this job..."}
              disabled={loading || !apiClient}
              validator={validateChatMessage}
              validateOnBlur={false}
              validateOnChange={true}
              errorText={validationError}
              onKeyDown={handleKeyDown}
            />
          </div>
          <Button
            variant="primary"
            onClick={handleSendMessage}
            disabled={!message.trim() || loading || !apiClient || !!validationError}
            loading={loading}
          >
            {t('ui.job-chat-panel.send')}
          </Button>
        </SpaceBetween>
      </div>
    </Modal>
  );
};

export default JobChatPanel;
