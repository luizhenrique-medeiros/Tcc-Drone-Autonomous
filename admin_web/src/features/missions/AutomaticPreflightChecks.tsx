import { CheckCircle2, CircleX, TriangleAlert } from 'lucide-react';
import type { Mission, VehicleHealth } from '../../services';
import {
  getAutomaticPreflightChecks,
  type AutomaticPreflightSeverity,
} from './vehicle-readiness';

interface AutomaticPreflightChecksProps {
  mission: Mission;
  health: VehicleHealth | null;
  compact?: boolean;
}

const severityMeta: Record<
  AutomaticPreflightSeverity,
  { icon: typeof CheckCircle2; label: string }
> = {
  PASS: { icon: CheckCircle2, label: 'PASS' },
  WARNING: { icon: TriangleAlert, label: 'WARNING' },
  BLOCKING: { icon: CircleX, label: 'BLOCKING' },
};

export function AutomaticPreflightChecks({
  mission,
  health,
  compact = false,
}: AutomaticPreflightChecksProps) {
  const checks = getAutomaticPreflightChecks(mission, health);
  const blockers = checks.filter((check) => check.severity === 'BLOCKING').length;
  const warnings = checks.filter((check) => check.severity === 'WARNING').length;

  return (
    <section
      className={`automatic-preflight${compact ? ' automatic-preflight--compact' : ''}`}
      aria-label="Verificações automáticas"
    >
      <header className="automatic-preflight__header">
        <div>
          <strong>Verificações automáticas</strong>
          <small>Nova validação será feita pelo backend ao autorizar.</small>
        </div>
        <span className="automatic-preflight__summary">
          {blockers > 0
            ? `${blockers} bloqueio${blockers === 1 ? '' : 's'}`
            : warnings > 0
              ? `${warnings} aviso${warnings === 1 ? '' : 's'}`
              : 'Tudo pronto'}
        </span>
      </header>
      <ul className="automatic-preflight__list">
        {checks.map((check) => {
          const meta = severityMeta[check.severity];
          const Icon = meta.icon;
          return (
            <li
              className={`automatic-preflight__item automatic-preflight__item--${check.severity.toLowerCase()}`}
              key={check.code}
            >
              <Icon aria-hidden="true" size={18} />
              <div>
                <strong>{check.label}</strong>
                <small>{check.detail}</small>
              </div>
              <span className="automatic-preflight__badge">{meta.label}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
