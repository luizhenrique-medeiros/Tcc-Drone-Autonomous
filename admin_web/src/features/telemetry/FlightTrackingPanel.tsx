import { useCallback, useEffect, useState } from 'react';
import { SatelliteMap } from '../../components/SatelliteMap';
import { Button, Card, Feedback, Modal } from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { adminApi, getErrorMessage, type Mission, type ObservedFlight, type Vehicle } from '../../services';
import { formatDateTime, formatDistance, formatOptionalNumber } from '../../utils/format';

const phaseLabels: Record<ObservedFlight['phase'], string> = {
  WAITING: 'Aguardando observações do voo',
  ARMED: 'Armado · decolagem não determinada',
  ARMED_ON_GROUND: 'Armado em solo',
  TAKING_OFF: 'Decolando',
  AIRBORNE: 'Em voo',
  MANUAL: 'Voo manual ou assistido',
  MISSION: 'Missão em execução',
  PAUSED: 'Missão pausada',
  RETURNING: 'Retornando',
  LANDING: 'Pousando',
  LANDED: 'Pousado',
  DISARMED: 'Desarmado',
};

function flightStatus(flight: ObservedFlight): string {
  if (flight.normal_completion) return 'Voo encerrado · missão concluída normalmente';
  if (flight.ended_at) {
    return flight.events.some((event) => event.event_type === 'FLIGHT_ENDED')
      ? 'Voo encerrado · conclusão normal não confirmada'
      : 'Acompanhamento encerrado';
  }
  if (flight.early_return && flight.phase === 'RETURNING') return 'Retorno antecipado';
  return phaseLabels[flight.phase];
}

const landedLabels: Record<number, string> = {
  1: 'Em solo',
  2: 'Em voo',
  3: 'Decolando',
  4: 'Pousando',
};

function itemLabel(flight: ObservedFlight, sequence: number): string {
  const protocol = `MAVLink ${sequence}`;
  if (!flight.mapping_current) return protocol;
  if (sequence === flight.destination_sequence) return `Destino (${protocol})`;
  if (sequence === flight.return_sequence) return `Retorno (${protocol})`;
  return protocol;
}

function FlightReadout({ flight, degraded }: { flight: ObservedFlight; degraded: boolean }) {
  const stale = flight.stale || degraded;
  const latestPoint = flight.point ?? flight.track.at(-1)?.at(-1);
  const canShowProgress = flight.link === 'OPERATOR' || flight.link === 'VERIFIED';
  const flightWasObserved = ['TAKING_OFF', 'AIRBORNE', 'MANUAL', 'MISSION', 'PAUSED', 'RETURNING', 'LANDING', 'LANDED'].includes(flight.phase)
    || flight.events.some((event) => event.event_type === 'FLIGHT_AIRBORNE' || event.event_type === 'FLIGHT_ENDED');
  return (
    <div className="stack">
      {stale ? <Feedback tone="warning">Telemetria desatualizada. Último estado conhecido.</Feedback> : null}
      {flight.ended_at ? <Feedback tone="info">Acompanhamento encerrado. Os dados abaixo são históricos.</Feedback> : null}
      {flight.link === 'UNASSOCIATED' && flightWasObserved
        ? <Feedback tone="info">Voo observado sem missão associada</Feedback> : null}
      {flight.link === 'OPERATOR' ? (
        <Feedback tone="info">
          Vínculo declarado pelo administrador. Revisão {flight.revision} associada por {flight.associated_by} em {formatDateTime(flight.associated_at)}.
          A correspondência dos itens com o arquivo ainda está sem verificação.
        </Feedback>
      ) : null}
      {flight.link === 'VERIFIED' ? flight.mapping_current
        ? <Feedback tone="success">Itens correspondentes à revisão {flight.revision} verificada da missão.</Feedback>
        : <Feedback tone="info">A revisão {flight.revision} tem um vínculo verificado anterior. O identificador do plano atual está indisponível.</Feedback>
        : null}
      {flight.link === 'DIVERGENT' ? <Feedback tone="warning">Identidade, plano a bordo ou revisão divergente. O vínculo dos itens foi suspenso.</Feedback> : null}
      <dl className="data-list telemetry-current">
        <div><dt>Acompanhamento da missão</dt><dd>{flightStatus(flight)}{flight.estimated ? ' · estimado' : ''}</dd></div>
        <div><dt>Veículo associado</dt><dd>{flight.vehicle_name ?? flight.vehicle_id}{flight.source === 'HARDWARE_REAL' ? ' · Hardware real' : flight.source === 'SITL' ? ' · SITL' : ''}</dd></div>
        <div><dt>Estado da aeronave</dt><dd>{flight.landed_state === null ? 'Indisponível' : landedLabels[flight.landed_state] ?? 'Indisponível'}</dd></div>
        <div><dt>Última atualização</dt><dd>{flight.last_seen_at ? formatDateTime(flight.last_seen_at) : 'Indisponível'}</dd></div>
        <div><dt>Modo PX4</dt><dd>{flight.mode ?? 'Indisponível'}</dd></div>
        <div><dt>Armamento</dt><dd>{flight.armed === null ? 'Indisponível' : flight.armed ? 'Armado' : 'Desarmado'}</dd></div>
        <div><dt>Altitude relativa</dt><dd>{flight.altitude_m === null ? 'Indisponível' : `${formatOptionalNumber(flight.altitude_m)} m`}</dd></div>
        <div><dt>Velocidade em solo</dt><dd>{flight.speed_m_s === null ? 'Indisponível' : `${formatOptionalNumber(flight.speed_m_s)} m/s`}</dd></div>
        {canShowProgress ? (
          <>
            <div><dt>Distância em linha reta ao destino</dt><dd>{flight.distance_m === null ? 'Indisponível' : formatDistance(flight.distance_m)}</dd></div>
            <div><dt>Item atual</dt><dd>{flight.sequence === null ? 'Sequência em execução indisponível' : itemLabel(flight, flight.sequence)}</dd></div>
            <div><dt>Itens alcançados</dt><dd>{flight.reached_sequences.length ? flight.reached_sequences.map((item) => itemLabel(flight, item)).join(', ') : 'Nenhum item confirmado'}</dd></div>
            <div><dt>Chegada ao destino</dt><dd>{flight.destination === 'CONFIRMED' ? 'Waypoint confirmado' : flight.destination === 'ESTIMATED' ? 'Proximidade estimada por posição' : 'Sem confirmação'}</dd></div>
          </>
        ) : null}
      </dl>
      {canShowProgress && flight.phase === 'RETURNING' && !flight.early_return && flight.destination === null
        ? <small>Retorno observado. A passagem pelo destino ficou sem confirmação.</small> : null}
      {flight.landed_state === null && flight.last_seen_at ? <small>Estado de solo, decolagem ou pouso do PX4 indisponível (EXTENDED_SYS_STATE).</small> : null}
      {canShowProgress && flight.mission_state === null && flight.last_seen_at ? <small>Estado interno da missão indisponível (MISSION_CURRENT). Pausa e conclusão podem ficar sem confirmação.</small> : null}
      {latestPoint ? (
        <SatelliteMap
          title={flight.point && !stale && !flight.ended_at ? 'Posição e trajeto observado' : 'Última posição e trajeto observado'}
          points={[{ ...latestPoint, label: 'Drone' }]}
          routeSegments={flight.track}
          height={320}
        />
      ) : <small>Posição indisponível (GLOBAL_POSITION_INT).</small>}
      {flight.events.length ? (
        <div>
          <h3>Eventos do voo</h3>
          <ol className="timeline">
            {flight.events.map((event) => (
              <li key={event.id} className="timeline__item">
                <div><strong>{event.message}</strong><small>{formatDateTime(event.metadata?.observed_at ?? event.created_at)}</small></div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}

type FlightPanelProps = { mission: Mission; vehicleId?: never } | { mission?: never; vehicleId: string };

export function OrderFlightSummary({ missionId, deliveryLabel }: { missionId: string; deliveryLabel: string }) {
  const load = useCallback(() => adminApi.getMissionFlight(missionId), [missionId]);
  const { data: flight, error, reload, isLoading } = useAsyncData(load);

  useEffect(() => {
    const timer = window.setInterval(() => void reload(), 3000);
    return () => window.clearInterval(timer);
  }, [reload]);

  return (
    <Card title="Acompanhamento e entrega">
      <dl className="data-list single-column">
        <div><dt>Voo observado</dt><dd>{flight ? flightStatus(flight) : error ? 'Indisponível' : isLoading ? 'Carregando' : 'Sem acompanhamento registrado'}</dd></div>
        <div><dt>Entrega física</dt><dd>{deliveryLabel}</dd></div>
      </dl>
      {flight?.ended_at ? <small>Encerrado em {formatDateTime(flight.ended_at)} · registro histórico</small> : null}
      {error || flight?.stale ? <Feedback tone="warning">Dados do acompanhamento desatualizados ou indisponíveis.</Feedback> : null}
    </Card>
  );
}

export function FlightTrackingPanel({ mission, vehicleId }: FlightPanelProps) {
  const missionId = mission?.id;
  const load = useCallback(() => missionId ? adminApi.getMissionFlight(missionId) : adminApi.getVehicleFlight(vehicleId!), [missionId, vehicleId]);
  const { data: flight, error, reload, setData, lastSuccessAt } = useAsyncData(load);
  const [selectionOpen, setSelectionOpen] = useState(false);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selected, setSelected] = useState('');
  const [selectionError, setSelectionError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const timer = window.setInterval(() => void reload(), 3000);
    return () => window.clearInterval(timer);
  }, [reload]);

  const chooseVehicle = async () => {
    setSelectionOpen(true);
    setSelected('');
    setVehicles([]);
    setSelectionError('');
    setBusy(true);
    try {
      setVehicles((await adminApi.listVehicles()).filter((vehicle) =>
        vehicle.autopilot_system.toUpperCase() === 'PX4'
        && ['HARDWARE_REAL', 'SITL'].includes(vehicle.operational_source)
        && vehicle.connected,
      ));
    } catch (failure) {
      setSelectionError(getErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  const associate = async () => {
    if (!mission?.file_hash || !selected) return;
    setBusy(true);
    setSelectionError('');
    try {
      const result = await adminApi.trackMission(mission.id, selected, mission.version, mission.file_hash);
      if (result) setData(result);
      setSelectionOpen(false);
      await reload();
    } catch (failure) {
      setSelectionError(getErrorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Acompanhamento do voo" action={mission?.qgroundcontrol_plan_exported_at && (!flight || flight.ended_at)
      ? <Button size="small" variant="secondary" onClick={() => void chooseVehicle()}>Acompanhar esta missão</Button>
      : undefined}>
      {error ? <Feedback tone="warning">Falha ao atualizar o acompanhamento. {error}</Feedback> : null}
      {flight ? <FlightReadout flight={flight} degraded={Boolean(error)} /> :
        <p>{lastSuccessAt ? 'Nenhum voo associado ou observado nesta tela.' : 'Aguardando dados do acompanhamento.'}</p>}
      {mission ? (
        <Modal open={selectionOpen} title="Acompanhar esta missão" onClose={() => setSelectionOpen(false)} closeDisabled={busy}
          footer={<><Button variant="secondary" disabled={busy} onClick={() => setSelectionOpen(false)}>Cancelar</Button>
            <Button loading={busy} disabled={!selected} onClick={() => void associate()}>Confirmar acompanhamento</Button></>}>
          <p>Acompanhe no site a revisão {mission.version} com o veículo selecionado. A operação continua no QGroundControl.</p>
          <div className="field">
            <label htmlFor="tracking-vehicle">Veículo PX4</label>
            <select id="tracking-vehicle" className="select" value={selected} disabled={busy} onChange={(event) => setSelected(event.target.value)}>
              <option value="">{busy ? 'Carregando veículos…' : vehicles.length ? 'Selecione o veículo' : 'Nenhum PX4 real ou SITL conectado'}</option>
              {vehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.name} · {vehicle.operational_source === 'SITL' ? 'SITL' : 'Hardware real'} · {vehicle.identifier}</option>)}
            </select>
          </div>
          {selectionError ? <Feedback tone="error">{selectionError}</Feedback> : null}
        </Modal>
      ) : null}
    </Card>
  );
}
