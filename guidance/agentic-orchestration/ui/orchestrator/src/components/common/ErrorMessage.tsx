// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { Alert, Box, Button, SpaceBetween } from '@cloudscape-design/components';

import { useTranslation } from 'react-i18next';
interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onRetry }) => {
  const { t } = useTranslation();
  return (
    <div className="error-container">
      <Alert
        statusIconAriaLabel="Error"
        type={t("common.errors.application_error")}
        header={t("common.errors.application_error")}
        action={
        onRetry &&
        <Button onClick={onRetry} variant="primary">
              {t('common.error-message.retry')}
            </Button>

        }>

        <SpaceBetween direction="vertical" size="s">
          <Box>{message}</Box>
          {!onRetry &&
          <Box color="text-status-inactive">
              {t('common.error-message.refresh-or-contact')}
            </Box>
          }
        </SpaceBetween>
      </Alert>
    </div>);

};

export default ErrorMessage;
