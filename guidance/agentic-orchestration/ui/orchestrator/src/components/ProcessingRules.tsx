import React, { useState, useEffect } from 'react';
import { getApiClient } from '../services/apiClient';
import { useTranslation } from 'react-i18next';
import './ProcessingRules.css';

interface ProcessingRule {
  document_id: string;
  document_type: string;
  sender_name: string;
  sender_address: string;
  status: 'ACTIVE' | 'PENDING REVIEW' | 'ARCHIVED';
  instructions_s3_uri: string;
  processing_workflow: string;
  example_document_uri: string;
  notes: string;
}

export const ProcessingRules: React.FC = () => {
  const { t } = useTranslation();
  const [rules, setRules] = useState<ProcessingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    try {
      setLoading(true);
      setError(null);
      const apiClient = getApiClient();
      const response = await apiClient.getProcessingRules(100);
      setRules(response.documents || []);
    } catch (err) {
      setError('Failed to load processing rules');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const searchRules = async () => {
    if (!searchTerm.trim()) {
      loadRules();
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const apiClient = getApiClient();
      const response = await apiClient.searchProcessingRules({
        sender_name: searchTerm
      });
      setRules(response.matches || []);
    } catch (err) {
      setError('Failed to search processing rules');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const toggleStatus = async (documentId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'ACTIVE' ? 'PENDING REVIEW' : 'ACTIVE';

    try {
      const apiClient = getApiClient();
      await apiClient.updateProcessingRule(documentId, {
        status: newStatus
      });

      // Update local state
      setRules(rules.map((rule) =>
      rule.document_id === documentId ?
      { ...rule, status: newStatus as any } :
      rule
      ));
    } catch (err) {
      setError('Failed to update status');
      console.error(err);
    }
  };

  const openInstructionsEditor = (instructionsUri: string, senderName: string) => {
    // Extract the S3 key from the URI
    const s3Key = instructionsUri.replace('s3://agenticidp-objects-395842723587/', '');

    // Open in new window with editor
    const editorUrl = `/instructions-editor?key=${encodeURIComponent(s3Key)}&sender=${encodeURIComponent(senderName)}`;
    window.open(editorUrl, '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'ACTIVE':return 'status-badge status-active';
      case 'PENDING REVIEW':return 'status-badge status-pending';
      case 'ARCHIVED':return 'status-badge status-archived';
      default:return 'status-badge';
    }
  };

  return (
    <div className="processing-rules-container">
      <div className="rules-header">
        <h1>{t("ui.processing-rules.title")}</h1>
        <p className="rules-subtitle">{t("ui.processing-rules.description")}</p>
      </div>

      <div className="search-bar">
        <input
          type="text"
          placeholder={t("ui.processing-rules.search-placeholder")}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && searchRules()}
          className="search-input" />

        <button onClick={searchRules} className="search-button">
          {t('ui.processing-rules.search')}
        </button>
        <button onClick={loadRules} className="clear-button">
          {t('ui.processing-rules.clear')}
        </button>
      </div>

      {error &&
      <div className="error-message">
          {error}
        </div>
      }

      {loading ?
      <div className="loading">{t('ui.processing-rules.loading')}</div> :

      <div className="rules-table-container">
          <table className="rules-table">
            <thead>
              <tr>
                <th>{t('ui.processing-rules.sender')}</th>
                <th>{t('ui.processing-rules.document-type')}</th>
                <th>{t('ui.processing-rules.address')}</th>
                <th>{t('ui.processing-rules.status')}</th>
                <th>{t('ui.processing-rules.instructions')}</th>
                <th>{t('ui.processing-rules.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {rules.length === 0 ?
            <tr>
                  <td colSpan={6} className="no-results">
                    {t('ui.processing-rules.no-rules-found')}
                  </td>
                </tr> :

            rules.map((rule) =>
            <tr key={rule.document_id}>
                    <td className="sender-name">{rule.sender_name}</td>
                    <td>{rule.document_type}</td>
                    <td className="address">{rule.sender_address}</td>
                    <td>
                      <span className={getStatusBadgeClass(rule.status)}>
                        {rule.status}
                      </span>
                    </td>
                    <td>
                      <button
                  onClick={() => openInstructionsEditor(rule.instructions_s3_uri, rule.sender_name)}
                  className="edit-button">

                        {t('ui.processing-rules.view-edit-instructions')}
                      </button>
                    </td>
                    <td>
                      <button
                  onClick={() => toggleStatus(rule.document_id, rule.status)}
                  className="toggle-button"
                  disabled={rule.status === 'ARCHIVED'}>

                        {rule.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
            )
            }
            </tbody>
          </table>
        </div>
      }

      <div className="rules-footer">
        <p>{t("ui.processing-rules.total")} {rules.length} processing rule{rules.length !== 1 ? 's' : ''}</p>
      </div>
    </div>);

};