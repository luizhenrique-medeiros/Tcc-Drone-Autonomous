import { useState } from 'react';
import { Button, Card, Feedback } from '../../design-system/components';
import { useAsyncData } from '../../hooks/useAsyncData';
import { adminApi } from '../../services';
import { px4SitlApi } from '../../services/real-api';
import { shortId } from '../../utils/format';
import { Px4SitlControls } from '../missions/Px4SitlControls';

async function loadArmTargets() {
  const vehicles = (await adminApi.listVehicles()).filter((vehicle) =>
    vehicle.operational_source === 'SITL' &&
    vehicle.autopilot_system.trim().toUpperCase() === 'PX4' &&
    vehicle.connected,
  );
  if (vehicles.length === 0) return [];

  const verified = await px4SitlApi.verifiedMissions();
  const details = await Promise.all(
    verified
      .filter((mission) => vehicles.some((vehicle) => vehicle.id === mission.vehicle_id))
      .map((mission) => adminApi.getMission(mission.id)),
  );
  return details.flatMap((mission) => {
    const vehicle = vehicles.find((item) => item.id === mission.vehicle_id);
    return vehicle && mission.status === 'VERIFIED' && mission.qgroundcontrol_sitl_review_event_id
      ? [{ mission, vehicle }]
      : [];
  });
}

export function SitlArmTest() {
  const { data: targets, isLoading, error, reload } = useAsyncData(loadArmTargets);
  const [missionId, setMissionId] = useState('');
  const target = !error && targets?.find(({ mission }) => mission.id === missionId);

  const missionPicker = (
    <>
      <div className="field">
        <label htmlFor="arm-test-mission">Missão verificada no simulador</label>
        <select
          className="select"
          id="arm-test-mission"
          value={target ? missionId : ''}
          disabled={!targets?.length || Boolean(error)}
          onChange={(event) => setMissionId(event.target.value)}
        >
          <option value="">Selecione uma missão</option>
          {targets?.map(({ mission, vehicle }) => (
            <option value={mission.id} key={mission.id}>
              #{shortId(mission.id)} · v{mission.version} · {vehicle.name}
            </option>
          ))}
        </select>
      </div>
      <div className="decision-actions">
        <Button variant="secondary" size="small" loading={isLoading} onClick={() => void reload()}>
          Atualizar missões de teste
        </Button>
      </div>
    </>
  );

  if (target) {
    return (
      <Px4SitlControls
        key={target.mission.id}
        mission={target.mission}
        vehicle={target.vehicle}
        onChange={() => void reload()}
        armOnly
      >
        {missionPicker}
      </Px4SitlControls>
    );
  }

  return (
    <Card title="Teste de armamento · PX4 SITL">
      <div className="stack">
        {error ? <Feedback tone="error">{error}</Feedback> : null}
        {targets?.length === 0 && !error ? (
          <Feedback>Conecte o PX4 SITL no ambiente de teste e verifique uma missão para habilitar o armamento.</Feedback>
        ) : null}
        {missionPicker}
        <div className="decision-actions">
          <Button variant="secondary" disabled>Armar drone</Button>
        </div>
      </div>
    </Card>
  );
}
