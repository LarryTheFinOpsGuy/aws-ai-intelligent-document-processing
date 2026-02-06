// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Authenticator, ThemeProvider } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import '@cloudscape-design/global-styles/index.css';

import { AppProvider } from './contexts/AppContext';
import { SessionProvider } from './contexts/SessionContext';
import MainLayout from './components/layout/MainLayout';

import './App.css';

const App: React.FC = () => {
  return (
    <ThemeProvider>
      <Authenticator.Provider>
        <AppProvider>
          <SessionProvider>
            <BrowserRouter>
              <div className="orchestrator-app">
                <MainLayout />
              </div>
            </BrowserRouter>
          </SessionProvider>
        </AppProvider>
      </Authenticator.Provider>
    </ThemeProvider>
  );
};

export default App;