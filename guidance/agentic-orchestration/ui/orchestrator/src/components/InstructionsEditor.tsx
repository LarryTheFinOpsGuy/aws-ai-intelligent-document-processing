import React, { useState, useEffect } from 'react';
import { getApiClient } from '../services/apiClient';
import { useTranslation } from 'react-i18next';
import './InstructionsEditor.css';

interface InstructionsEditorProps {
  s3Key: string;
  senderName: string;
}

export const InstructionsEditor: React.FC<InstructionsEditorProps> = ({
  s3Key, senderName }) => {
  const { t } = useTranslation();
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadContent();
  }, [s3Key]);

  const loadContent = async () => {
    try {
      setLoading(true);
      setError(null);
      const apiClient = getApiClient();
      const response = await apiClient.getInstructionsContent(s3Key);
      setContent(response.content || '');
    } catch (err) {
      setError('Failed to load instructions content');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const saveContent = async () => {
    try {
      setSaving(true);
      setError(null);
      const apiClient = getApiClient();
      await apiClient.saveInstructionsContent(s3Key, content);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError('Failed to save instructions content');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="instructions-editor">
        <div className="loading">{t("ui.instructions-editor.loading-instructions")}</div>
      </div>);

  }

  return (
    <div className="instructions-editor">
      <div className="editor-header">
        <h1>{t("ui.instructions-editor.instructions-title")}{senderName}</h1>
        <div className="editor-actions">
          <button
            onClick={saveContent}
            disabled={saving}
            className="save-button">

            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {saved && <span className="save-success">✓ Saved</span>}{t("ui.instructions-editor.saved")}
        </div>
      </div>

      {error &&
      <div className="error-message">
          {error}
        </div>
      }

      <div className="editor-content">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="content-editor"
          placeholder={t("ui.instructions-editor.enter-instructions")}
          disabled={saving} />

      </div>

      <div className="editor-footer">
        <p className="file-path">{t("ui.instructions-editor.file")}{s3Key}</p>
        <p className="format-info">{t("ui.instructions-editor.markdown-format-help")}

        </p>
      </div>
    </div>);

};