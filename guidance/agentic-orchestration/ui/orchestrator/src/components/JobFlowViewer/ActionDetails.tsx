import React from 'react';
import { Box, SpaceBetween } from '@cloudscape-design/components';

import { useTranslation } from 'react-i18next';
interface JobAction {
  job_id: string;
  started_at: string;
  completed_at?: string;
  agent: string;
  result: string;
  success: boolean;
}

interface ActionDetailsProps {
  action: JobAction | null;
  formatDuration: (startDate?: string, stopDate?: string) => string;
}

const ActionDetails: React.FC<ActionDetailsProps> = ({ action, formatDuration }) => {
  const { t } = useTranslation();
  if (!action) {
    return (
      <Box textAlign="center" padding="l" color="text-status-inactive">{t("ui.actions.select_to_view_details")}

      </Box>);

  }

  return (
    <div className="action-details">
      <SpaceBetween size="l">
        <Box>
          <Box variant="h3">{action.agent}</Box>
        </Box>

        <div className="action-metadata">
          <SpaceBetween direction="horizontal" size="l">
            <Box>
              <Box variant="awsui-key-label">{t('ui.action-details.status')}</Box>
              <Box className={`action-status action-status-${action.success ? 'succeeded' : 'failed'}`}>
                {!action.completed_at ? 'Running' : action.success ? 'Completed' : 'Failed'}
              </Box>
            </Box>
            <Box>
              <Box variant="awsui-key-label">{t('ui.action-details.duration')}</Box>
              <Box>{formatDuration(action.started_at, action.completed_at)}</Box>
            </Box>
            <Box>
              <Box variant="awsui-key-label">{t('ui.action-details.started')}</Box>
              <Box>{new Date(action.started_at).toLocaleString()}</Box>
            </Box>
            {action.completed_at &&
            <Box>
                <Box variant="awsui-key-label">{t('ui.action-details.completed')}</Box>
                <Box>{new Date(action.completed_at).toLocaleString()}</Box>
              </Box>
            }
          </SpaceBetween>
        </div>

        <Box>
          <Box variant="h4" margin={{ bottom: 's' }}>{t('ui.action-details.result')}</Box>
          <Box>
            <pre className="action-result">{action.result}</pre>
          </Box>
        </Box>
      </SpaceBetween>
    </div>);

};

export default ActionDetails;
