import { useEffect, useRef, useState } from 'react';
import { OperationalSourceBadge } from '../../components/OperationalSourceBadge';
import { Button, Feedback, Modal } from '../../design-system/components';
import type {
  ArmMissionInput,
  Mission,
  Vehicle,
  VehicleHealth,
} from '../../services';
import {
  formatDateTime,
  formatNullableText,
  formatOptionalNumber,
  shortId,
} from '../../utils/format';
import { HoldToConfirmButton } from './HoldToConfirmButton';

interface ArmVehicleDialogProps {
  open: boolean;
  mission: Mission;
  vehicle: Vehicle | null;
  health: VehicleHealth | null;
  blockers: string[];
  isSubmitting: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (input: ArmMissionInput) => Promise<void>;
}

export function ArmVehicleDialog({
  open,
  mission,
  vehicle,
  health,
  blockers,
  isSubmitting,
  error,
  onClose,
  onSubmit,
}: ArmVehicleDialogProps) {
  const [reason, setReason] = useState('');
  const [areaClear, setAreaClear] = useState(false);
  const [operatorPresent, setOperatorPresent] = useState(false);
  const [safetySwitchReady, setSafetySwitchReady] = useState(false);
  const submissionLock = useRef(false);

  useEffect(() => {
    if (!open) return;
    setReason('');
    setAreaClear(false);
    setOperatorPresent(false);
    setSafetySwitchReady(false);
    submissionLock.current = false;
  }, [open]);

  const canSubmit =
    blockers.length === 0 &&
    reason.trim().length >= 10 &&
    areaClear &&
    operatorPresent &&
    safetySwitchReady &&
    !isSubmitting;

  const submit = async () => {
    if (!canSubmit || submissionLock.current) return;
    submissionLock.current = true;
    try {
      await onSubmit({
        reason: reason.trim(),
        area_clear_confirmed: true,
        operator_present_confirmed: true,
        safety_switch_ready_confirmed: true,
      });
    } finally {
      submissionLock.current = false;
    }
  };

  return (
    <Modal
      open={open}
      title="Solicitar armamento padrão?"
      onClose={onClose}
      closeDisabled={isSubmitting}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <HoldToConfirmButton
            disabled={!canSubmit}
            loading={isSubmitting}
            onConfirm={submit}
          />
        </>
      }
    >
      <div className="arm-dialog stack">
        <Feedback tone="error">
          <strong>Ação física crítica e auditada.</strong>
          <p>
            Esta solicitação usa somente o armamento padrão do ArduPilot e respeita
            todos os checks de pré-armamento e failsafes. Não existe opção de
            contorno nesta tela.
          </p>
        </Feedback>

        <dl className="data-list authorization-summary">
          <div>
            <dt>Missão</dt>
            <dd>#{shortId(mission.id)} · v{mission.version}</dd>
          </div>
          <div>
            <dt>Veículo</dt>
            <dd>{vehicle ? `${vehicle.name} · ${vehicle.identifier}` : '--'}</dd>
          </div>
          <div>
            <dt>Modo / estado</dt>
            <dd>
              {formatNullableText(health?.flight_mode)} ·{' '}
              {health?.armed === false
                ? 'Desarmado'
                : health?.armed === true
                  ? 'ARMADO'
                  : 'Armamento --'}
            </dd>
          </div>
          <div>
            <dt>Heartbeat</dt>
            <dd>
              {health?.heartbeat_ok === true ? 'Atual' : 'Não confirmado'} · idade{' '}
              {formatOptionalNumber(health?.heartbeat_age_seconds, {
                maximumFractionDigits: 1,
              })}s
            </dd>
          </div>
          <div>
            <dt>Última leitura</dt>
            <dd>{formatDateTime(health?.received_at)}</dd>
          </div>
          <div>
            <dt>Origem técnica</dt>
            <dd>{health ? <OperationalSourceBadge {...health} /> : '--'}</dd>
          </div>
        </dl>

        {blockers.length > 0 ? (
          <Feedback tone="error">
            <strong>Armamento bloqueado:</strong>
            <ul>
              {blockers.map((blocker) => (
                <li key={blocker}>{blocker}</li>
              ))}
            </ul>
          </Feedback>
        ) : null}

        <fieldset className="checklist-fieldset">
          <legend>Confirmações presenciais</legend>
          <div className="stack checklist-list">
            <div className="check-row">
              <input
                id="arm-area-clear"
                type="checkbox"
                checked={areaClear}
                onChange={(event) => setAreaClear(event.target.checked)}
              />
              <label htmlFor="arm-area-clear">
                <strong>Área ao redor do veículo livre e controlada</strong>
                <small>Pessoas e objetos estão fora da área dos motores.</small>
              </label>
            </div>
            <div className="check-row">
              <input
                id="arm-operator-present"
                type="checkbox"
                checked={operatorPresent}
                onChange={(event) => setOperatorPresent(event.target.checked)}
              />
              <label htmlFor="arm-operator-present">
                <strong>Operador presente junto ao veículo</strong>
                <small>
                  O operador acompanha fisicamente o veículo e possui meio imediato
                  de interromper a operação.
                </small>
              </label>
            </div>
            <div className="check-row">
              <input
                id="arm-safety-switch-ready"
                type="checkbox"
                checked={safetySwitchReady}
                onChange={(event) =>
                  setSafetySwitchReady(event.target.checked)
                }
              />
              <label htmlFor="arm-safety-switch-ready">
                <strong>Safety switch pronto para uso</strong>
                <small>
                  O operador confirmou o estado do safety switch e pode desarmar
                  imediatamente se necessário.
                </small>
              </label>
            </div>
          </div>
        </fieldset>

        <div className="field">
          <label htmlFor="arm-reason">Justificativa operacional</label>
          <textarea
            className="textarea"
            id="arm-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            minLength={10}
            maxLength={500}
            placeholder="Ex.: armamento presencial para iniciar a missão revisada."
          />
        </div>
        {error ? <Feedback tone="error">{error}</Feedback> : null}
      </div>
    </Modal>
  );
}
