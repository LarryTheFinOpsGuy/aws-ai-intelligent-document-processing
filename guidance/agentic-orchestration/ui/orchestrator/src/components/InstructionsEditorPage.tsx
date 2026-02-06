import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { InstructionsEditor } from './InstructionsEditor';

import { useTranslation } from 'react-i18next';
export const InstructionsEditorPage: React.FC = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const s3Key = searchParams.get('key');
  const senderName = searchParams.get('sender');

  if (!s3Key || !senderName) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>{t("ui.errors.missing_parameters")}
        <h2>{t("ui.instructions-editor-page.invalid-url")}</h2>
        <p>{t("ui.errors.missing_parameters")}</p>
      </div>);

  }

  return <InstructionsEditor s3Key={s3Key} senderName={senderName} />;
};