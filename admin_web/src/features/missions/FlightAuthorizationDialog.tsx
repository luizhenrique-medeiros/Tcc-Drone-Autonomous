import { ShieldCheck, TriangleAlert } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { OperationalSourceBadge } from '../../components/OperationalSourceBadge';
import {
  Button,
  Feedback,
  Modal,
} from '../../design-system/components';
import type {
  FlightAuthorizationInput,
  Mission,
  PreflightChecklist,
  Vehicle,
  VehicleHealth,
} from '../../services';
import {
  formatDistance,
  formatNullableText,
  formatOptionalNumber,
  formatPercent,
  shortId,
} from '../../utils/format';
import { getVehicleReadiness } from './vehicle-readiness';

const initialChecklist: PreflightChecklist = {
  mission_reviewed: false,
  route_matches_destination: false,
  controlled_area_confirmed: false,
  weather_checked: false,
  payload_secured: false,
  people_clear: false,
  operator_ready: false,
  rtl_area_clear: false,
};

const checklistLabels: Array<{
  key: keyof PreflightChecklist;
  title: string;
  description: string;
}> = [
  {
    key: 'mission_reviewed',
    title: 'Missão revisada no Mission Planner',
    description: 'Arquivo, versão e sequência de waypoints conferidos.',
  },
  {
    key: 'route_matches_destination',
    title: 'Rota corresponde ao ponto final do cliente',
    description: 'Latitude e longitude finais foram comparadas.',
  },
  {
    key: 'controlled_area_confirmed',
    title: 'Área de operação controlada',
    description: 'Acesso de terceiros está restrito durante toda a missão.',
  },
  {
    key: 'weather_checked',
    title: 'Condições meteorológicas verificadas',
    description: 'Vento, chuva e visibilidade estão dentro do procedimento local.',
  },
  {
    key: 'payload_secured',
    title: 'Carga fixada e mecanismo conferido',
    description: 'Peso e fixação foram validados pelo operador.',
  },
  {
    key: 'people_clear',
    title: 'Áreas de decolagem e destino livres',
    description: 'Nenhuma pessoa permanece no perímetro de segurança.',
  },
  {
    key: 'operator_ready',
    title: 'Operador responsável presente',
    description: 'Operador acompanha Mission Planner e está pronto para intervir.',
  },
  {
    key: 'rtl_area_clear',
    title: 'Área de retorno e RTL livre',
    description: 'Origem, altitude RTL e área de pouso foram confirmadas.',
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
  const [checklist, setChecklist] = useState(initialChecklist);
  const [operatorName, setOperatorName] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const requiredPhrase = `AUTORIZAR VOO ${shortId(mission.id)}`;
  const readiness = getVehicleReadiness(health);
  const allChecked = useMemo(
    () => Object.values(checklist).every(Boolean),
    [checklist],
  );
  const canSubmit =
    readiness.ready &&
    vehicle !== null &&
    allChecked &&
    operatorName.trim().length >= 3 &&
    confirmation.trim() === requiredPhrase;

  useEffect(() => {
    if (!open) return;
    setChecklist(initialChecklist);
    setOperatorName('');
    setConfirmation('');
  }, [open]);

  const submit = async () => {
    if (!canSubmit || !vehicle) return;
    await onSubmit({
      vehicle_id: vehicle.id,
      operator_name: operatorName.trim(),
      controlled_area_confirmed: true,
      checklist,
    });
  };

  return (
    <Modal
      open={open}
      title="Autorizar envio e execução do voo"
      onClose={onClose}
      closeDisabled={isSubmitting}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancelar
          </Button>
          <Button
            variant="warning"
            onClick={() => void submit()}
            loading={isSubmitting}
            disabled={!canSubmit}
          >
            <ShieldCheck size={18} /> Autorizar voo uma única vez
          </Button>
        </>
      }
    >
      <div className="authorization-form stack">
        <Feedback tone="warning">
          <strong>Segunda autorização — ação crítica e auditada.</strong>
          <p>
            Esta etapa pode liberar o gateway para enviar e executar a versão {mission.version}
            da missão. A autorização expira e não pode ser reutilizada.
          </p>
        </Feedback>

        <dl className="data-list authorization-summary">
          <div><dt>Missão</dt><dd>#{shortId(mission.id)} · v{mission.version}</dd></div>
          <div><dt>Distância</dt><dd>{formatDistance(mission.estimated_distance_m)}</dd></div>
          <div><dt>Altitude</dt><dd>{mission.altitude_m} m</dd></div>
          <div><dt>Veículo</dt><dd>{vehicle?.name ?? 'Nenhum disponível'}</dd></div>
          <div><dt>Origem técnica</dt><dd>{health ? <OperationalSourceBadge {...health} /> : '--'}</dd></div>
          <div><dt>Bateria</dt><dd>{health ? formatPercent(health.battery_percent) : '--'}</dd></div>
          <div><dt>GPS / EKF</dt><dd>{health ? `${formatNullableText(health.gps_fix)} · ${formatOptionalNumber(health.satellites)} sat. · ${health.ekf_ok === true ? 'EKF OK' : health.ekf_ok === false ? 'EKF inválido' : 'EKF --'}` : '--'}</dd></div>
        </dl>

        {!readiness.ready ? (
          <Feedback tone="error">
            <TriangleAlert size={18} />
            <div>
              <strong>Veículo não atende aos requisitos mínimos.</strong>
              <p>{readiness.blockers.join(' ')}</p>
            </div>
          </Feedback>
        ) : null}

        <fieldset className="checklist-fieldset">
          <legend>Checklist pré-voo obrigatório</legend>
          <div className="stack checklist-list">
            {checklistLabels.map((item) => (
              <div className="check-row" key={item.key}>
                <input
                  id={`check-${item.key}`}
                  type="checkbox"
                  checked={checklist[item.key]}
                  onChange={(event) =>
                    setChecklist((current) => ({
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
          <label htmlFor="operator-name">Operador responsável presente</label>
          <input
            className="input"
            id="operator-name"
            value={operatorName}
            onChange={(event) => setOperatorName(event.target.value)}
            placeholder="Nome completo do operador"
            autoComplete="name"
          />
        </div>
        <div className="field confirmation-field">
          <label htmlFor="authorization-phrase">
            Para confirmar, digite <span className="mono">{requiredPhrase}</span>
          </label>
          <input
            className="input mono"
            id="authorization-phrase"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value.toUpperCase())}
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        {error ? <Feedback tone="error">{error}</Feedback> : null}
      </div>
    </Modal>
  );
}
