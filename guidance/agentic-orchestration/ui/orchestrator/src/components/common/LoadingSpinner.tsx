// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { Box, Spinner, SpaceBetween } from '@cloudscape-design/components';

interface LoadingSpinnerProps {
  message?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message = 'Loading...' }) => {
  return (
    <div className="loading-container">
      <SpaceBetween direction="vertical" size="m" alignItems="center">
        <Spinner size="large" />
        <Box variant="p" color="text-status-inactive">
          {message}
        </Box>
      </SpaceBetween>
    </div>
  );
};

export default LoadingSpinner;