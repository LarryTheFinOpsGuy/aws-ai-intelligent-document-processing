import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from '@cloudscape-design/components';

import TopNavigation from './layout/TopNavigation';
import SideNavigation from './layout/SideNavigation';
import OrchestrateTab from './tabs/OrchestrateTab';
import StatusTab from './tabs/StatusTab';
import ChatTab from './tabs/ChatTab';
import LogsTab from './tabs/LogsTab';
import { ProcessingRules } from './ProcessingRules';
import { InstructionsEditorPage } from './InstructionsEditorPage';

const AuthenticatedApp: React.FC = () => {
  const [navigationOpen, setNavigationOpen] = useState(false);

  return (
    <div className="authenticated-app">
      <TopNavigation />
      <AppLayout
        headerSelector="#top-navigation"
        navigationOpen={navigationOpen}
        onNavigationChange={({ detail }) => setNavigationOpen(detail.open)}
        navigation={<SideNavigation />}
        toolsHide
        content={
          <div className="main-content">
            <Routes>
              <Route path="/" element={<Navigate to="/orchestrate" replace />} />
              <Route path="/orchestrate" element={<OrchestrateTab />} />
              <Route path="/status" element={<StatusTab />} />
              <Route path="/chat" element={<ChatTab />} />
              <Route path="/logs" element={<LogsTab />} />
              <Route path="/processing-rules" element={<ProcessingRules />} />
              <Route path="/instructions-editor" element={<InstructionsEditorPage />} />
            </Routes>
          </div>
        }
      />
    </div>
  );
};

export default AuthenticatedApp;