import { AlertTriangle, ShieldAlert } from 'lucide-react';
import type { OperationalAlert } from '../services/operational-alerts';
import { formatDateTime } from '../utils/format';

export function OperationalAlerts({
  alerts,
  max = 5,
  emptyMessage,
}: {
  alerts: OperationalAlert[];
  max?: number;
  emptyMessage?: string;
}) {
  if (alerts.length === 0) {
    return emptyMessage ? (
      <p className="operational-alerts__empty">
        <ShieldAlert size={18} aria-hidden="true" /> {emptyMessage}
      </p>
    ) : null;
  }

  return (
    <div className="operational-alerts" aria-label="Alertas operacionais">
      {alerts.slice(0, max).map((alert) => (
        <article
          className={`operational-alert operational-alert--${alert.severity.toLowerCase()}`}
          key={alert.key}
        >
          <AlertTriangle size={18} aria-hidden="true" />
          <div>
            <div className="operational-alert__heading">
              <strong>{alert.title}</strong>
              <span>{alert.severity}</span>
            </div>
            <p>{alert.what}</p>
            <dl>
              <div><dt>Impacto</dt><dd>{alert.impact}</dd></div>
              <div><dt>Última atualização</dt><dd>{formatDateTime(alert.last_updated_at)}</dd></div>
              <div><dt>Ação recomendada</dt><dd>{alert.recommended_action}</dd></div>
            </dl>
            {alert.occurrences > 1 ? (
              <small>{alert.occurrences} ocorrências semelhantes agrupadas no cooldown.</small>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
