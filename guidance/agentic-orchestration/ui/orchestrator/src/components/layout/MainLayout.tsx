// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import { useTranslation } from 'react-i18next';

import { useApp } from '../../contexts/AppContext';
import AuthenticatedApp from '../AuthenticatedApp';
import LoadingSpinner from '../common/LoadingSpinner';
import ErrorMessage from '../common/ErrorMessage';
import NotificationSystem from '../common/NotificationSystem';
import NetworkStatus from '../common/NetworkStatus';

const MainLayout: React.FC = () => {
  const { t } = useTranslation();
  const { isAuthenticated, loading, error } = useApp();

  return (
    <div className="main-layout">
      <NotificationSystem />
      <NetworkStatus />
      
      {loading && <LoadingSpinner message="Initializing application..." />}
      
      {error && !loading && <ErrorMessage message={error} />}
      
      {!loading && !error && !isAuthenticated && (
        <Authenticator>
          {({ user: authUser }) => (
            <div>{t('ui.main-layout.welcome')} {authUser?.username}!</div>
          )}
        </Authenticator>
      )}
      
      {!loading && !error && isAuthenticated && <AuthenticatedApp />}
    </div>
  );
};

export default MainLayout;