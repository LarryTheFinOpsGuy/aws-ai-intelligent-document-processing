import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { SideNavigation as CloudscapeSideNavigation } from '@cloudscape-design/components';

const SideNavigation: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const navigationItems = [
    {
      type: 'section' as const,
      text: 'Main Sections',
      items: [
        {
          type: 'link' as const,
          text: 'Upload',
          href: '/orchestrate',
        },
        {
          type: 'link' as const,
          text: 'Jobs',
          href: '/status',
        },
        {
          type: 'link' as const,
          text: 'Chat',
          href: '/chat',
        },
      ],
    },
    {
      type: 'section' as const,
      text: 'Configuration',
      items: [
        {
          type: 'link' as const,
          text: 'Processing Rules',
          href: '/processing-rules',
        },
      ],
    },
  ];

  return (
    <CloudscapeSideNavigation
      activeHref={location.pathname}
      header={{
        href: '/',
        text: 'Modern Orchestrator UI',
      }}
      items={navigationItems}
      onFollow={(event) => {
        if (!event.detail.external) {
          event.preventDefault();
          navigate(event.detail.href);
        }
      }}
    />
  );
};

export default SideNavigation;