// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { Box, Spinner, SpaceBetween, StatusIndicator } from '@cloudscape-design/components';

interface LoadingIndicatorProps {
  size?: 'small' | 'normal' | 'large';
  message?: string;
  inline?: boolean;
  variant?: 'spinner' | 'status';
}

/**
 * Enhanced loading indicator component with multiple display options
 * Provides consistent loading states across the application
 */
const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ 
  size = 'normal', 
  message = 'Loading...', 
  inline = false,
  variant = 'spinner'
}) => {
  const content = variant === 'spinner' ? (
    <SpaceBetween direction={inline ? 'horizontal' : 'vertical'} size="s" alignItems="center">
      <Spinner size={size} />
      {message && (
        <Box 
          variant={inline ? 'span' : 'p'} 
          color="text-status-inactive"
          fontSize={size === 'small' ? 'body-s' : 'body-m'}
        >
          {message}
        </Box>
      )}
    </SpaceBetween>
  ) : (
    <StatusIndicator type="loading">
      {message}
    </StatusIndicator>
  );

  if (inline) {
    return <span className="loading-indicator-inline">{content}</span>;
  }

  return (
    <div className="loading-indicator-container" style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center',
      padding: size === 'large' ? '2rem' : '1rem'
    }}>
      {content}
    </div>
  );
};

export default LoadingIndicator;