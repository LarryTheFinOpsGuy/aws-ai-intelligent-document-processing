import React from 'react';
import { TopNavigation as CloudscapeTopNavigation } from '@cloudscape-design/components';

import { useAuth } from '../../hooks/useAuth';
import { useSession } from '../../contexts/SessionContext';

const TopNavigation: React.FC = () => {
  const { user, signOut } = useAuth();
  const { sessionState, generateNewSession } = useSession();

  const handleSignOut = () => {
    try {
      signOut();
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  const handleNewSession = () => {
    const newSessionId = generateNewSession();
    console.log('Generated new session:', newSessionId);
  };

  return (
    <div id="top-navigation">
      <CloudscapeTopNavigation
        identity={{
          href: '/',
          title: 'Modern Orchestrator UI',
          logo: {
            src: '/vite.svg',
            alt: 'Modern Orchestrator UI',
          },
        }}
        utilities={[
          {
            type: 'menu-dropdown',
            text: user?.username || 'User',
            description: user?.attributes?.email || '',
            iconName: 'user-profile',
            items: [
              {
                id: 'session-info',
                text: `Session: ${sessionState.sessionId.slice(0, 8)}...`,
                disabled: true,
              },
              { type: 'divider' },
              {
                id: 'new-session',
                text: 'New Session',
              },
              { type: 'divider' },
              {
                id: 'profile',
                text: 'Profile',
                href: '#',
              },
              {
                id: 'preferences',
                text: 'Preferences',
                href: '#',
              },
              { type: 'divider' },
              { id: 'signout', text: 'Sign out' },
            ],
            onItemClick: ({ detail }) => {
              switch (detail.id) {
                case 'new-session':
                  handleNewSession();
                  break;
                case 'signout':
                  handleSignOut();
                  break;
                default:
                  break;
              }
            },
          },
        ]}
      />
    </div>
  );
};

export default TopNavigation;