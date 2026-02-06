// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0

import React from 'react';
import { Flashbar, FlashbarProps } from '@cloudscape-design/components';
import { useApp } from '../../contexts/AppContext';

/**
 * Centralized notification system using Cloudscape Flashbar
 * Displays error messages, success confirmations, warnings, and info messages
 * with consistent styling and behavior across the application.
 */
const NotificationSystem: React.FC = () => {
  const { notifications, removeNotification } = useApp();

  // Transform our notification format to Cloudscape Flashbar format
  const flashbarItems: FlashbarProps.MessageDefinition[] = notifications.map((notification) => ({
    type: notification.type,
    header: notification.header,
    content: notification.content,
    dismissible: notification.dismissible,
    dismissLabel: notification.dismissLabel || 'Dismiss',
    onDismiss: notification.onDismiss || (() => removeNotification(notification.id)),
    ...(notification.action && {
      action: {
        buttonText: notification.action.buttonText,
        onButtonClick: notification.action.onButtonClick,
      }
    }),
    id: notification.id,
  }));

  return (
    <Flashbar
      items={flashbarItems}
      stackItems={true}
    />
  );
};

export default NotificationSystem;