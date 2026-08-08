import { ShieldCheck } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { OperationalSourceBadge } from '../../components/OperationalSourceBadge';
import { Button, Feedback, Modal } from '../../design-system/components';
import type {
  FlightAuthorizationInput,
  HumanFlightConfirmations,
  Mission,
  Vehicle,
  VehicleHealth,
} from '../../services';
import {
  formatCoordinate,
  formatDistance,
  formatNullableText,
  formatOptionalNumber,
  formatPercent,
  shortId,
} from '../../utils/format';
import { AutomaticPreflightChecks } from './AutomaticPreflightChecks';
import { getMissionReadiness } from './vehicle-readiness';

const initialConfirmations: HumanFlightConfirmations = {
  area_and_conditions_clear: false,
  aircraft_and_payload_inspected: false,
  operator_ready: false,
};

const confirmationLabels: Array<{
  key: keyof HumanFlightConfirmations;
  title: string;
  description: string;
}> = [
  {
    key: 'area_and_conditions_clear',
    title: 'Área e condições de voo livres e controladas',
    description:
      'Pessoas, decolagem, destino, clima e área de retorno/RTL estão livres ou sob controle.',
  },
  {
    key: 'aircraft_and_payload_inspected',
    title: 'Drone, carga e mecanismo inspecionados',
    description: 'Aeronave, fixação, peso e mecanismo de entrega foram conferidos.',
  },
  {
    key: 'operator_ready',
    title: 'Operador pronto para iniciar',
    description: 'O operador acompanha o voo e está preparado para intervir.',
  },
];

interface FlightAuthorizationDialogProps {
  open: boolean;
  mission: Mission;
  vehicle: Vehicle | null;
  health: VehicleHealth | null;
  isSubmitting: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (input: FlightAuthorizationInput) => Promise<void>;
}

export function FlightAuthorizationDialog({
  open,
  mission,
  vehicle,
  health,
  isSubmitting,
  error,
  onClose,
  onSubmit,
}: FlightAuthorizationDialogProps) {
  const [confirmations, setConfirmations] = useState(initialConfirmations);
  const [operatorName, setOperatorName] = useState('');
  const submissionLock = useRef(false);
  const readiness = getMissionReadiness(mission, health);
  const allChecked = useMemo(
    () => Object.values(confirmations).every(Boolean),
    [confirmations],
  );
  const canSubmit =
    readiness.ready &&
    vehicle !== null &&
    allChecked &&
    operatorName.trim().length >= 3 &&
    !isSubmitting;

  useEffect(() => {
    if (!open) return;
    setConfirmations(initialConfirmations);
    setOperatorName('');
    submissionLock.current = false;
  }, [open]);

  const submit = async () => {
    if (!canSubmit || !vehicle || submissionLock.current) return;
    submissionLock.current = true;
    try {
      await onSubmit({
        vehicle_id: vehicle.id,
        operator_name: operatorName.trim(),
        controlled_area_confirmed: true,
        checklist: confirmations,
      });
    } finally {
      submissionLock.current = false;
    }
  };

  const gpsEkfSummary = health
    ? `${formatNullableText(health.gps_fix)} · ${formatOptionalNumber(health.satellites)} sat. · ${
        health.ekf_ok === true
          ? 'EKF OK'
          : health.ekf_ok === false
            ? 'EKF inválido'
            : 'EKF --'
      }`
    : '--';
  const modeAndArming = health
    ? `${formatNullableText(health.flight_mode)} · ${
        health.armed === false
          ? 'Desarmado'
          : health.armed === true
            ? 'ARMADO'
            : 'Armamento --'
      }`
    : '--';
  const hashSummary = mission.file_hash
    ? `${mission.file_hash.slice(0, 12)}…`
    : '--';

  return (
    <Modal
      open={open}
      title="Autorizar esta missão?"
      onClose={onClose}
      closeDisabled={isSubmitting}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button
            onClick={() => void submit()}
            loading={isSubmitting}
            disabled={!canSubmit}
          >
            <ShieldCheck size={18} /> Autorizar missão
          </Button>
        </>
      }
    >
      <div className="authorization-form stack">
        <Feedback tone="warning">
          <strong>Autorização crítica, auditada e de uso único.</strong>
          <p>
            Ela fica vinculada à versão {mission.version}, ao veículo e ao operador abaixo.
            O backend repetirá as validações antes de emitir a autorização.
          </p>
        </Feedback>

        <dl className="data-list authorization-summary">
          <div>
            <dt>Pedido</dt>
            <dd>#{shortId(mission.order_id)}</dd>
          </div>
          <div>
            <dt>Destino</dt>
            <dd>
              {mission.destination.label ?? 'Ponto final'} ·{' '}
              <span className="mono">
                {formatCoordinate(mission.destination.latitude)},{' '}
                {formatCoordinate(mission.destination.longitude)}
              </span>
            </dd>
          </div>
          <div>
            <dt>Distância</dt>
            <dd>{formatDistance(mission.estimated_distance_m)}</dd>
          </div>
          <div>
            <dt>Veículo / status</dt>
            <dd>{vehicle ? `${vehicle.name} · ${vehicle.status}` : 'Nenhum disponível'}</dd>
          </div>
          <div>
            <dt>Modo / armamento</dt>
            <dd>{modeAndArming}</dd>
          </div>
          <div>
            <dt>Bateria</dt>
            <dd>{health ? formatPercent(health.battery_percent) : '--'}</dd>
          </div>
          <div>
            <dt>GPS / EKF</dt>
            <dd>{gpsEkfSummary}</dd>
          </div>
          <div>
            <dt>Versão / hash</dt>
            <dd>
              v{mission.version} · <span className="mono">{hashSummary}</span>
            </dd>
          </div>
          <div>
            <dt>Origem técnica</dt>
            <dd>{health ? <OperationalSourceBadge {...health} /> : '--'}</dd>
          </div>
        </dl>

        <AutomaticPreflightChecks mission={mission} health={health} compact />

        <fieldset className="checklist-fieldset">
          <legend>Confirmações do operador</legend>
          <div className="stack checklist-list">
            {confirmationLabels.map((item) => (
              <div className="check-row" key={item.key}>
                <input
                  id={`check-${item.key}`}
                  type="checkbox"
                  checked={confirmations[item.key]}
                  onChange={(event) =>
                    setConfirmations((current) => ({
                      ...current,
                      [item.key]: event.target.checked,
                    }))
                  }
                />
                <label htmlFor={`check-${item.key}`}>
                  <strong>{item.title}</strong>
                  <small>{item.description}</small>
                </label>
              </div>
            ))}
          </div>
        </fieldset>

        <div className="field">
          <label htmlFor="operator-name">Nome do operador responsável</label>
          <input
            className="input"
            id="operator-name"
            value={operatorName}
            onChange={(event) => setOperatorName(event.target.value)}
            placeholder="Nome completo do operador"
            autoComplete="name"
          />
        </div>
        {error ? <Feedback tone="error">{error}</Feedback> : null}
      </div>
    </Modal>
  );
}
