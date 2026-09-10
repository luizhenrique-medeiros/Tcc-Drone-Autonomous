import { useEffect, useRef, useState } from 'react';
import { Button, Feedback, Modal } from '../../design-system/components';
import type { Mission, MissionOriginRevisionInput, VehicleHealth } from '../../services';

import { canReviseOrigin } from './origin-revision-readiness';

interface Props {
  open: boolean;
  mission: Mission;
  health: VehicleHealth | null;
  busy: boolean;
  error: string;
  onClose: () => void;
  onSubmit: (input: MissionOriginRevisionInput) => Promise<void>;
}

export function OriginRevisionDialog({ open, mission, health, busy, error, onClose, onSubmit }: Props) {
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const sample = useRef(health);
  sample.current = health;
  const submissionLock = useRef(false);
  useEffect(() => {
    if (!open) return;
    setLatitude(sample.current?.current_latitude?.toFixed(7) ?? '');
    setLongitude(sample.current?.current_longitude?.toFixed(7) ?? '');
    setReason('');
    setConfirmed(false);
  }, [open, mission.id, mission.version]);
  const coordinatesValid = latitude.trim() !== '' && longitude.trim() !== ''
    && Number.isFinite(Number(latitude)) && Math.abs(Number(latitude)) <= 90
    && Number.isFinite(Number(longitude)) && Math.abs(Number(longitude)) <= 180;
  const canSubmit = canReviseOrigin(mission, health) && coordinatesValid && confirmed
    && reason.trim().length >= 10 && !busy;
  const submit = async () => {
    if (!canSubmit || submissionLock.current) return;
    submissionLock.current = true;
    try {
      await onSubmit({
        expected_version: mission.version, expected_sha256: mission.file_hash!,
        origin_latitude: Number(latitude).toFixed(7), origin_longitude: Number(longitude).toFixed(7),
        reason: reason.trim(), position_confirmed: confirmed,
      });
    } finally { submissionLock.current = false; }
  };
  return <Modal open={open} title="Atualizar origem e retorno" onClose={onClose} closeDisabled={busy}
    footer={<><Button variant="secondary" onClick={onClose} disabled={busy}>Cancelar</Button>
      <Button onClick={() => void submit()} disabled={!canSubmit} loading={busy}>Gerar nova versão</Button></>}>
    <div className="stack">
      <Feedback tone="warning">A versão {mission.version} será arquivada. A nova rota exigirá exportação, revisão e autorização próprias. Não envia comandos ao drone nem altera Home/RTL no piloto automático.</Feedback>
      <p>Destino preservado: {mission.destination.latitude.toFixed(7)}, {mission.destination.longitude.toFixed(7)}.</p>
      <p>O GPS apenas preenche uma sugestão. Confira o ponto definitivo de decolagem e retorno antes de salvar.</p>
      <div className="field"><label htmlFor="revision-latitude">Latitude da nova origem</label>
        <input id="revision-latitude" className="input" value={latitude} disabled={busy} onChange={(event) => { setLatitude(event.target.value); setConfirmed(false); }} /></div>
      <div className="field"><label htmlFor="revision-longitude">Longitude da nova origem</label>
        <input id="revision-longitude" className="input" value={longitude} disabled={busy} onChange={(event) => { setLongitude(event.target.value); setConfirmed(false); }} /></div>
      <div className="field"><label htmlFor="revision-reason">Motivo da mudança de origem</label>
        <textarea id="revision-reason" className="textarea" value={reason} minLength={10} maxLength={1000} disabled={busy} onChange={(event) => setReason(event.target.value)} /></div>
      <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={(event) => setConfirmed(event.target.checked)} /> Confirmo estas coordenadas para decolagem e retorno; o destino permanece igual.</label>
      {!canReviseOrigin(mission, health) ? <Feedback tone="error">Aguarde saúde fresca, veículo desarmado em STABILIZE e os quatro gates desligados.</Feedback> : null}
      {error ? <Feedback tone="error">{error}</Feedback> : null}
    </div>
  </Modal>;
}
