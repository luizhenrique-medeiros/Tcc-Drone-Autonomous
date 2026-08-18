import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DEMO_ORDERS } from '../src/demo/data';
import { MissionPage } from '../src/features/missions/MissionPage';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const apiMocks = vi.hoisted(() => ({
  getMission: vi.fn(),
  getOrder: vi.fn(),
  listVehicles: vi.fn(),
  getVehicleHealth: vi.fn(),
}));

vi.mock('../src/services', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services')>()),
  adminApi: apiMocks,
}));

vi.mock('../src/hooks/useOperationsStream', () => ({
  useOperationsStream: () => 'connected',
}));

vi.mock('../src/components/SatelliteMap', () => ({
  SatelliteMap: () => <div data-testid="satellite-map" />,
}));

const renderMission = () =>
  render(
    <MemoryRouter initialEntries={['/missions/mission-start']}>
      <Routes>
        <Route path="/missions/:missionId" element={<MissionPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('barreira visual do START', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getMission.mockResolvedValue({
      ...readyMission,
      id: 'mission-start',
      order_id: DEMO_ORDERS[0].id,
      vehicle_id: readyVehicle.id,
      status: 'VERIFIED',
    });
    apiMocks.getOrder.mockResolvedValue(DEMO_ORDERS[0]);
    apiMocks.listVehicles.mockResolvedValue([readyVehicle]);
  });

  it('habilita START somente com flags, link atual e armamento confirmado', async () => {
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      armed: true,
    });

    renderMission();

    expect(await screen.findByRole('button', { name: 'Solicitar START' })).toBeEnabled();
  });

  it.each([
    {
      overrides: { flight_commands_enabled: false },
      title: /ALLOW_FLIGHT_COMMANDS está desabilitado/i,
    },
    {
      overrides: { mission_start_enabled: false },
      title: /ALLOW_MISSION_START está desabilitado/i,
    },
    {
      overrides: { armed: false },
      title: /operador ainda não confirmou armamento físico/i,
    },
  ])('bloqueia START quando uma barreira explícita não foi satisfeita', async ({
    overrides,
    title,
  }) => {
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      armed: true,
      ...overrides,
    });

    renderMission();

    expect(await screen.findByRole('button', { name: 'Solicitar START' })).toBeDisabled();
    expect(screen.getByTitle(title)).toBeInTheDocument();
  });

  it('bloqueia START quando o snapshot está vencido', async () => {
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      armed: true,
      is_stale: true,
    });

    renderMission();

    expect(await screen.findByRole('button', { name: 'Solicitar START' })).toBeDisabled();
    expect(screen.getByTitle(/leitura de saúde está vencida/i)).toBeInTheDocument();
  });

  it('bloqueia START sem conexão ou heartbeat atual', async () => {
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      armed: true,
      connected: false,
      heartbeat_ok: false,
    });

    renderMission();

    expect(await screen.findByRole('button', { name: 'Solicitar START' })).toBeDisabled();
    expect(screen.getByTitle(/sem conexão ou heartbeat atual/i)).toBeInTheDocument();
  });

  it('bloqueia START quando o snapshot pertence a outro veículo', async () => {
    apiMocks.getMission.mockResolvedValue({
      ...readyMission,
      id: 'mission-start',
      order_id: DEMO_ORDERS[0].id,
      vehicle_id: 'vehicle-not-loaded',
      status: 'VERIFIED',
    });
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      armed: true,
    });

    renderMission();

    expect(await screen.findByRole('button', { name: 'Solicitar START' })).toBeDisabled();
    expect(screen.getByTitle(/não pertence ao veículo vinculado/i)).toBeInTheDocument();
  });
});
