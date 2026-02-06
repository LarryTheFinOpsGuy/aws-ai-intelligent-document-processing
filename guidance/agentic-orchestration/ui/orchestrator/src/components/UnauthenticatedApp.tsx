import React from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import { Box, Header } from '@cloudscape-design/components';

import { useTranslation } from 'react-i18next';
const UnauthenticatedApp: React.FC = () => {
  const { t } = useTranslation();
  return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" padding="xl">
      <div style={{ maxWidth: '400px', width: '100%' }}>
        <Header variant="h1" description={t("ui.general.sign_in_prompt")}>
          {t("ui.general.app_title")}
        </Header>
        <Box marginTop="l">
          <Authenticator />
        </Box>
      </div>
    </Box>);

};

export default UnauthenticatedApp;
