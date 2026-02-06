import React from 'react';
import { Box } from '@cloudscape-design/components';
import { useTranslation } from 'react-i18next';
import {
  FaSearch,
  FaLink,
  FaFileCode,
  FaRobot,
  FaCheckCircle,
  FaTools,
  FaWrench,
  FaSave,
  FaCog } from
'react-icons/fa';

interface JobAction {
  job_id: string;
  started_at: string;
  completed_at?: string;
  agent: string;
  result: string;
  success: boolean;
}

interface FlowDiagramProps {
  actions: JobAction[];
  selectedAction: JobAction | null;
  onActionClick: (action: JobAction) => void;
}

const getAgentIcon = (agentName: string, isComplete: boolean, success: boolean) => {
  const status = !isComplete ? 'running' : success ? 'succeeded' : 'failed';
  const iconProps = { size: 24, className: `agent-icon agent-icon-${status}` };

  const agentLower = agentName.toLowerCase();

  // nosemgrep: react-props-spreading
  if (agentLower.includes('analyzer')) return <FaSearch {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('matcher')) return <FaLink {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('instructions')) return <FaFileCode {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('extractor')) return <FaRobot {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('validator')) return <FaCheckCircle {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('troubleshooter')) return <FaTools {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('fixer')) return <FaWrench {...iconProps} />;
  // nosemgrep: react-props-spreading
  if (agentLower.includes('save')) return <FaSave {...iconProps} />;

  // nosemgrep: react-props-spreading
  return <FaCog {...iconProps} />;
};

const getStatusClass = (action: JobAction) => {
  if (!action.completed_at) return 'running';
  return action.success ? 'succeeded' : 'failed';
};

const FlowDiagram: React.FC<FlowDiagramProps> = ({ actions, selectedAction, onActionClick }) => {
  const { t } = useTranslation();
  if (!actions || actions.length === 0) {
    return (
      <Box textAlign="center" padding="xl">{t("ui.actions.no_actions_available")}
        <Box variant="p" color="text-status-inactive">{t("ui.actions.no_actions_available")}</Box>
      </Box>);

  }

  return (
    <div className="flow-diagram">
      <div className="flow-container">
        {actions.map((action, index) => {
          const statusClass = getStatusClass(action);
          const isSelected = selectedAction?.started_at === action.started_at;
          const isComplete = !!action.completed_at;

          return (
            <React.Fragment key={`${action.agent}-${action.started_at}`}>
              <div
                className={`flow-step ${statusClass} ${isSelected ? 'selected' : ''}`}
                onClick={() => onActionClick(action)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onActionClick(action);
                  }
                }}
                role="button"
                tabIndex={0}>

                <div className="step-icon-container">
                  {getAgentIcon(action.agent, isComplete, action.success)}
                  {!isComplete && <div className="step-pulse-ring" />}
                </div>
                <div className="step-label">
                  <div className="step-name">{action.agent}</div>
                  <div className={`step-status-text status-text-${statusClass}`}>
                    {!isComplete ? t('ui.flow-diagram.running') : action.success ? t('ui.flow-diagram.completed') : t('ui.flow-diagram.failed')}
                  </div>
                </div>
                <div className="step-progress">
                  <div
                    className={`step-progress-bar ${statusClass}`}
                    style={{ width: isComplete ? '100%' : '75%' }} />

                </div>
              </div>

              {index < actions.length - 1 &&
              <div className="flow-arrow">
                  <div className="arrow-line">
                    <div className="arrow-animation" />
                  </div>
                  <div className="arrow-head" />
                </div>
              }
            </React.Fragment>);

        })}
      </div>

      <div className="flow-legend">
        <div className="legend-item">
          <div className="legend-icon succeeded" />
          <span>{t('ui.flow-diagram.completed')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-icon running" />
          <span>{t('ui.flow-diagram.running')}</span>
        </div>
        <div className="legend-item">
          <div className="legend-icon failed" />
          <span>{t('ui.flow-diagram.failed')}</span>
        </div>
      </div>
    </div>);

};

export default FlowDiagram;
