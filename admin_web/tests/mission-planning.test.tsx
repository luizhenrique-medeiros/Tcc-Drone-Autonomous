import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEMO_ORDERS } from '../src/demo/data';
import { MissionPage } from '../src/features/missions/MissionPage';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const api = vi.hoisted(() => ({
  getMission: vi.fn(),
  getOrder: vi.fn(),
  listVehicles: vi.fn(),
  getVehicleHealth: vi.fn(),
  exportQgcDraft: vi.fn(),
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
    api.listVehicles.mockResolvedValue([]);
    api.exportQgcDraft.mockResolvedValue(undefined);
  });

  it('exporta o rascunho sem veículo, telemetria ou altitude AMSL', async () => {
    const user = userEvent.setup();
    api.listVehicles.mockRejectedValue(new Error('Gateway indisponível'));
    renderMission();
    await user.click(await screen.findByRole('button', { name: 'Baixar plano do QGroundControl' }));
    expect(screen.getByText(/na origem planejada/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Baixar .plan' }));
    expect(await screen.findByText(/Rascunho .plan baixado/)).toBeInTheDocument();
    expect(api.exportQgcDraft).toHaveBeenCalledWith(mission.id, undefined, undefined);
  });

  it('trata o veículo como fonte de posição, sem validar aptidão ou mostrar controles de voo', async () => {
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
    await user.click(await screen.findByRole('button', { name: 'Baixar plano do QGroundControl' }));
    expect(screen.getByRole('button', { name: 'Baixar .plan' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /autorizar|armamento|start|abortar|solicitar rtl/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/Verificações automáticas|checklist/i)).not.toBeInTheDocument();
  });

  it('registra o arquivo escolhido e recupera a revisão atual para abrir no QGroundControl', async () => {
    const user = userEvent.setup();
    api.getMission
      .mockResolvedValueOnce(mission)
      .mockResolvedValue({ ...mission, qgroundcontrol_review_status: 'CURRENT' });
    api.recordQgcReview.mockResolvedValue({ plan_sha256: 'sha-test' });
    api.downloadReviewedQgcPlan.mockResolvedValue('missao-revisada.plan');
    renderMission();

    await user.click(await screen.findByRole('button', { name: 'Enviar plano revisado' }));
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
