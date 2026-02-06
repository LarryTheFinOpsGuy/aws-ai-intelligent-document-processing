// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React, { useState, useEffect } from 'react';
import { StatusIndicator, Box } from '@cloudscape-design/components';
import { useApp } from '../../contexts/AppContext';
import { checkNetworkConnectivity } from '../../utils/errorHandling';

import { useTranslation } from 'react-i18next';
/**
 * Network connectivity status indicator
 * Monitors online/offline status and displays appropriate indicators
 */
const NetworkStatus: React.FC = () => {
  const { t } = useTranslation();
  const { addNotification } = useApp();
  const [isOnline, setIsOnline] = useState(checkNetworkConnectivity());

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      addNotification({
        type: 'success',
        header: 'Connection Restored',
        content: 'Internet connection has been restored. You can now use all features.',
        dismissible: true
      });
    };

    const handleOffline = () => {
      setIsOnline(false);
      addNotification({
        type: 'warning',
        header: 'Connection Lost',
        content: 'Internet connection lost. Some features may not work until connection is restored.',
        dismissible: true
      });
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [addNotification]);

  if (isOnline) {
    return null; // Don't show anything when online
  }

  return (
    <Box margin="s">{t("common.errors.no_internet_connection")}
      <StatusIndicator type="warning">{t("common.errors.no_internet_connection")}

      </StatusIndicator>
    </Box>);

};

export default NetworkStatus;
