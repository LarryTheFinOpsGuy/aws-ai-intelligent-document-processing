import React from 'react';
import { useAuthenticator } from '@aws-amplify/ui-react';
import { Spinner, Box } from '@cloudscape-design/components';

import { useApp } from '../contexts/AppContext';
import AuthenticatedApp from './AuthenticatedApp';
import UnauthenticatedApp from './UnauthenticatedApp';

import { useTranslation } from 'react-i18next';
const AppContent: React.FC = () => {
  const { t } = useTranslation();
  const { authStatus } = useAuthenticator((context) => [context.authStatus]);
  const { loading, error } = useApp();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <Spinner size="large" />
      </Box>);

  }

  if (error) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" padding="xl">
        <div>{t("ui.errors.application_error")}
          <h2>{t("ui.errors.application_error")}</h2>
          <p>{error}</p>
        </div>
      </Box>);

  }

  if (authStatus === 'authenticated') {
    return <AuthenticatedApp />;
  }

  return <UnauthenticatedApp />;
};

export default AppContent;
