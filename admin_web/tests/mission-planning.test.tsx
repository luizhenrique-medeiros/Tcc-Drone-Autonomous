import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEMO_ORDERS } from '../src/demo/data';
import { MissionPage } from '../src/features/missions/MissionPage';
import { OrderFlightSummary } from '../src/features/telemetry/FlightTrackingPanel';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const api = vi.hoisted(() => ({
  getMission: vi.fn(),
  getOrder: vi.fn(),
  getMissionFlight: vi.fn(),
  trackMission: vi.fn(),
  listVehicles: vi.fn(),
  getVehicleHealth: vi.fn(),
  downloadQgcPlan: vi.fn(),
  recordQgcReview: vi.fn(),
  downloadReviewedQgcPlan: vi.fn(),
}));

vi.mock('../src/services', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services')>()),
  adminApi: api,
}));
vi.mock('../src/hooks/useOperationsStream', () => ({ useOperationsStream: () => 'connected' }));
vi.mock('../src/components/SatelliteMap', () => ({ SatelliteMap: () => <div data-testid="satellite-map" /> }));

const mission = {
  ...readyMission,
  order_id: DEMO_ORDERS[0].id,
  status: 'GENERATED',
};

function renderMission() {
  return render(
    <MemoryRouter initialEntries={[`/missions/${mission.id}`]}>
      <Routes><Route path="/missions/:missionId" element={<MissionPage />} /></Routes>
    </MemoryRouter>,
  );
}

describe('planejamento e revisão da missão', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    api.getMission.mockResolvedValue(mission);
    api.getOrder.mockResolvedValue(DEMO_ORDERS[0]);
    api.getMissionFlight.mockResolvedValue(null);
    api.listVehicles.mockResolvedValue([]);
    api.downloadQgcPlan.mockResolvedValue('pedido-v2.plan');
  });

  it('associa explicitamente uma revisão exportada ao PX4 selecionado', async () => {
    const user = userEvent.setup();
    api.getMission.mockResolvedValue({ ...mission, qgroundcontrol_plan_exported_at: '2026-11-24T19:00:00Z' });
    api.listVehicles.mockResolvedValue([
      readyVehicle,
      { ...readyVehicle, id: 'physical', name: 'Pixhawk da bancada', autopilot_system: 'PX4', operational_source: 'HARDWARE_REAL' },
    ]);
    api.trackMission.mockResolvedValue(null);
    renderMission();
    await user.click(await screen.findByRole('button', { name: 'Acompanhar esta missão' }));
    const select = await screen.findByLabelText('Veículo PX4');
    expect(await screen.findByRole('option', { name: /Pixhawk da bancada/ })).toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'Confirmar acompanhamento' });
    expect(confirm).toBeDisabled();
    await user.selectOptions(select, 'physical');
    await user.click(confirm);
    expect(api.trackMission).toHaveBeenCalledWith(mission.id, 'physical', mission.version, mission.file_hash);
  });

  it('identifica solo e desarmamento sem iniciar o acompanhamento do voo', async () => {
    api.getMissionFlight.mockResolvedValue({
      phase: 'WAITING', armed: false, landed_state: 1, link: 'OPERATOR', revision: 1,
      associated_by: 'Operador', vehicle_name: 'Pixhawk de bancada', source: 'HARDWARE_REAL',
      track: [], events: [], reached_sequences: [], point: null,
      distance_m: null, altitude_m: null, speed_m_s: null, mission_state: 1, sequence: null,
    });
    renderMission();
    expect(await screen.findByText('Em solo')).toBeInTheDocument();
    expect(screen.getByText('Desarmado')).toBeInTheDocument();
    expect(screen.getByText('Aguardando observações do voo')).toBeInTheDocument();
    expect(screen.getByText('Pixhawk de bancada · Hardware real')).toBeInTheDocument();
    expect(screen.getByText(/Vínculo declarado pelo administrador/)).toBeInTheDocument();
    expect(screen.queryByText('Missão em execução')).not.toBeInTheDocument();
  });

  it('exibe o voo encerrado no pedido com a entrega ainda pendente', async () => {
    api.getMissionFlight.mockResolvedValue({
      phase: 'DISARMED', ended_at: '2026-11-25T00:20:30Z', normal_completion: false,
      events: [{ event_type: 'FLIGHT_ENDED' }],
    });
    render(<OrderFlightSummary missionId={mission.id} deliveryLabel="Entrega aguardando confirmação" />);
    expect(await screen.findByText(/Voo encerrado/)).toBeInTheDocument();
    expect(screen.getByText('Entrega aguardando confirmação')).toBeInTheDocument();
    expect(screen.getByText(/registro histórico/)).toBeInTheDocument();
  });

  it('exibe como histórico o acompanhamento substituído antes do voo', async () => {
    api.getMissionFlight.mockResolvedValue({
      phase: 'WAITING', ended_at: '2026-11-25T00:20:30Z', normal_completion: false,
      events: [{ event_type: 'FLIGHT_ASSOCIATION_REPLACED' }],
    });
    render(<OrderFlightSummary missionId={mission.id} deliveryLabel="Entrega aguardando confirmação" />);
    expect(await screen.findByText('Acompanhamento encerrado')).toBeInTheDocument();
    expect(screen.queryByText('Aguardando observações do voo')).not.toBeInTheDocument();
    expect(screen.getByText(/registro histórico/)).toBeInTheDocument();
  });

  it('exporta o rascunho sem veículo, telemetria ou altitude AMSL', async () => {
    const user = userEvent.setup();
    api.listVehicles.mockRejectedValue(new Error('Gateway indisponível'));
    renderMission();
    await user.click(await screen.findByRole('button', { name: 'Baixar missão para QGroundControl' }));
    expect(screen.getByText(/na origem planejada/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Baixar .plan' }));
    expect(await screen.findByText(/pedido-v2.plan baixado/)).toBeInTheDocument();
    expect(api.downloadQgcPlan).toHaveBeenCalledWith(mission.id, mission.version, mission.file_hash, undefined);
    expect(api.listVehicles).not.toHaveBeenCalled();
  });

  it('mantém a origem da missão e a exportação disponível sem mostrar controles de voo', async () => {
    const user = userEvent.setup();
    api.getMission.mockResolvedValue({ ...mission, status: 'VERIFIED', vehicle_id: readyVehicle.id });
    api.listVehicles.mockResolvedValue([{ ...readyVehicle, autopilot_system: 'PX4' }]);
    api.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      source: 'HARDWARE_REAL',
      armed: true,
      gps_fix: 'SEM FIX',
      battery_percent: 0,
      preflight_ok: null,
      current_latitude: -23.1,
      current_longitude: -46.5,
    });
    renderMission();
    await user.click(await screen.findByRole('button', { name: 'Baixar missão para QGroundControl' }));
    expect(screen.getByRole('button', { name: 'Baixar .plan' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /autorizar|armamento|start|abortar|solicitar rtl/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Verificações automáticas|checklist/i)).not.toBeInTheDocument();
    expect(api.getVehicleHealth).not.toHaveBeenCalled();
  });

  it('registra o arquivo escolhido e recupera a revisão atual para abrir no QGroundControl', async () => {
    const user = userEvent.setup();
    api.getMission
      .mockResolvedValueOnce(mission)
      .mockResolvedValue({ ...mission, qgroundcontrol_review_status: 'CURRENT' });
    api.recordQgcReview.mockResolvedValue({ plan_sha256: 'sha-test' });
    api.downloadReviewedQgcPlan.mockResolvedValue('missao-revisada.plan');
    renderMission();

    await user.click(await screen.findByRole('button', { name: 'Registrar arquivo revisado' }));
    const file = new File(['{}'], 'missao.plan', { type: 'application/json' });
    Object.defineProperty(file, 'text', { value: async () => '{}' });
    await user.upload(screen.getByLabelText('Arquivo .plan revisado'), file);
    await user.click(screen.getByRole('button', { name: 'Registrar plano revisado' }));
    expect(await screen.findByText(/Plano revisado registrado/)).toBeInTheDocument();
    expect(api.recordQgcReview).toHaveBeenCalledWith(mission.id, mission.version, mission.file_hash, '{}');

    await user.click(screen.getByRole('button', { name: 'Baixar plano revisado para o QGroundControl' }));
    expect(await screen.findByText(/missao-revisada\.plan baixado/)).toBeInTheDocument();
    expect(api.downloadReviewedQgcPlan).toHaveBeenCalledWith(mission.id);
  });
});
