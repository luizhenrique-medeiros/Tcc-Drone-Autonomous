import { useState } from 'react';
import { Card, PageHeader } from '../../design-system/components';
import { benchModePreference } from '../../services/session';

export function SettingsPage() {
  const [benchMode, setBenchMode] = useState(benchModePreference.get);

  return (
    <div className="stack">
      <PageHeader eyebrow="Painel administrativo" title="Configurações" />
      <Card title="Modo bancada">
        <div className="check-row">
          <input
            id="bench-mode"
            type="checkbox"
            checked={benchMode}
            aria-describedby="bench-mode-description"
            onChange={(event) => {
              const enabled = event.target.checked;
              benchModePreference.set(enabled);
              setBenchMode(enabled);
            }}
          />
          <div>
            <label htmlFor="bench-mode"><strong>Ativar modo bancada</strong></label>
            <small id="bench-mode-description">
              Com a Pixhawk desarmada e em recepção passiva, GPS, posição, Home e RTL
              aparecem como informativos. Avisos esperados de GPS ficam no histórico.
              A opção vale para esta sessão do painel.
            </small>
          </div>
        </div>
      </Card>
    </div>
  );
}
