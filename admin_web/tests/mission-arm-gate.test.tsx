import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DEMO_ORDERS } from '../src/demo/data';
import { MissionPage } from '../src/features/missions/MissionPage';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const apiMocks = vi.hoisted(() => ({
  getMission: vi.fn(),
  getOrder: vi.fn(),
  listVehicles: vi.fn(),
  getVehicleHealth: vi.fn(),
  armMission: vi.fn(),
  getMissionCommand: vi.fn(),
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
    <MemoryRouter initialEntries={['/missions/mission-arm']}>
      <Routes>
        <Route path="/missions/:missionId" element={<MissionPage />} />
      </Routes>
    </MemoryRouter>,
  );

const renderMissionWithNavigation = () =>
  render(
    <MemoryRouter initialEntries={['/missions/mission-arm']}>
      <Link to="/missions/mission-other">Trocar missão</Link>
      <Routes>
        <Route path="/missions/:missionId" element={<MissionPage />} />
      </Routes>
    </MemoryRouter>,
  );

const verifiedArmMission = {
  ...readyMission,
  id: 'mission-arm',
  order_id: DEMO_ORDERS[0].id,
  vehicle_id: readyVehicle.id,
  status: 'VERIFIED' as const,
};

const pendingArmCommand = {
  id: 'command-arm',
  mission_id: verifiedArmMission.id,
  command: 'ARM' as const,
  reason: 'Armamento presencial da missão verificada',
  status: 'PENDING' as const,
  gateway_id: null,
  requested_at: '2026-08-21T12:00:00Z',
  acknowledged_at: null,
  completed_at: null,
  result_detail: null,
};

describe('barreira visual do armamento', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getMission.mockResolvedValue(verifiedArmMission);
    apiMocks.getOrder.mockResolvedValue(DEMO_ORDERS[0]);
    apiMocks.listVehicles.mockResolvedValue([readyVehicle]);
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      vehicle_arm_enabled: true,
      flight_mode: 'STABILIZE',
      armed: false,
    });
  });

  afterEach(() => vi.useRealTimers());

  it('oferece o botão em VERIFIED e revalida antes de abrir o diálogo', async () => {
    const user = userEvent.setup();
    renderMission();

    const armButton = await screen.findByRole('button', {
      name: 'Solicitar armamento',
    });
    expect(armButton).toBeEnabled();
    await user.click(armButton);

    expect(
      await screen.findByRole('dialog', {
        name: 'Solicitar armamento padrão?',
      }),
    ).toBeInTheDocument();
    await waitFor(() => expect(apiMocks.getVehicleHealth).toHaveBeenCalledTimes(2));
  });

  it('mostra motivo visível quando o gate dedicado está fechado', async () => {
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      vehicle_arm_enabled: false,
      flight_mode: 'STABILIZE',
      armed: false,
    });
    renderMission();

    expect(
      await screen.findByRole('button', { name: 'Solicitar armamento' }),
    ).toBeDisabled();
    expect(
      screen.getByText(/gate dedicado de armamento está desabilitado/i),
    ).toBeInTheDocument();
  });

  it('não mostra a ação fora do estado VERIFIED', async () => {
    apiMocks.getMission.mockResolvedValue({
      ...readyMission,
      id: 'mission-arm',
      order_id: DEMO_ORDERS[0].id,
      vehicle_id: readyVehicle.id,
      status: 'UPLOADED',
    });
    renderMission();

    await screen.findByRole('heading', { name: /Missão #MISSION-/ });
    expect(
      screen.queryByRole('button', { name: 'Solicitar armamento' }),
    ).not.toBeInTheDocument();
  });

  it('acompanha o comando exato e mostra result_detail assim que ele falha', async () => {
    const user = userEvent.setup();
    apiMocks.armMission.mockResolvedValue({
      mission: verifiedArmMission,
      command: pendingArmCommand,
    });
    apiMocks.getMissionCommand.mockResolvedValue({
      ...pendingArmCommand,
      status: 'FAILED',
      completed_at: '2026-08-21T12:00:02Z',
      result_detail: 'COMMAND_ACK recusou o armamento',
    });
    renderMission();

    await user.click(
      await screen.findByRole('button', { name: 'Solicitar armamento' }),
    );
    fireEvent.change(screen.getByLabelText('Justificativa operacional'), {
      target: { value: pendingArmCommand.reason },
    });
    const confirmations = screen.getAllByRole('checkbox');
    fireEvent.click(confirmations[0]);
    fireEvent.click(confirmations[1]);
    fireEvent.click(confirmations[2]);

    vi.useFakeTimers();
    fireEvent.pointerDown(
      screen.getByRole('button', {
        name: 'Segure para solicitar armamento',
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
      await Promise.resolve();
    });

    expect(apiMocks.armMission).toHaveBeenCalledTimes(1);
    expect(apiMocks.getMissionCommand).toHaveBeenCalledWith(
      verifiedArmMission.id,
      pendingArmCommand.id,
    );
    expect(
      screen.getByText('COMMAND_ACK recusou o armamento'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Armamento confirmado pelo comando concluído/i),
    ).not.toBeInTheDocument();
  });

  it('revalida o snapshot imediatamente antes do POST e bloqueia se ele ficou stale', async () => {
    const user = userEvent.setup();
    const armableHealth = {
      ...readyHealth,
      flight_commands_enabled: true,
      mission_start_enabled: true,
      vehicle_arm_enabled: true,
      flight_mode: 'STABILIZE',
      armed: false,
    };
    apiMocks.getVehicleHealth
      .mockResolvedValueOnce(armableHealth)
      .mockResolvedValueOnce(armableHealth)
      .mockResolvedValueOnce({ ...armableHealth, is_stale: true });
    renderMission();

    await user.click(
      await screen.findByRole('button', { name: 'Solicitar armamento' }),
    );
    fireEvent.change(screen.getByLabelText('Justificativa operacional'), {
      target: { value: pendingArmCommand.reason },
    });
    screen.getAllByRole('checkbox').forEach((checkbox) =>
      fireEvent.click(checkbox),
    );

    vi.useFakeTimers();
    fireEvent.pointerDown(
      screen.getByRole('button', {
        name: 'Segure para solicitar armamento',
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
      await Promise.resolve();
    });

    expect(apiMocks.getVehicleHealth).toHaveBeenCalledTimes(3);
    expect(apiMocks.armMission).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Armamento bloqueado após revalidação.*snapshot vencido/i),
    ).toBeInTheDocument();
  });

  it('cancela o polling ativo quando o missionId da rota muda', async () => {
    const user = userEvent.setup();
    apiMocks.getMission.mockImplementation(async (id: string) => ({
      ...verifiedArmMission,
      id,
    }));
    apiMocks.armMission.mockResolvedValue({
      mission: verifiedArmMission,
      command: pendingArmCommand,
    });
    apiMocks.getMissionCommand.mockResolvedValue(pendingArmCommand);
    renderMissionWithNavigation();

    await user.click(
      await screen.findByRole('button', { name: 'Solicitar armamento' }),
    );
    fireEvent.change(screen.getByLabelText('Justificativa operacional'), {
      target: { value: pendingArmCommand.reason },
    });
    screen.getAllByRole('checkbox').forEach((checkbox) =>
      fireEvent.click(checkbox),
    );

    vi.useFakeTimers();
    fireEvent.pointerDown(
      screen.getByRole('button', {
        name: 'Segure para solicitar armamento',
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
      await Promise.resolve();
    });
    expect(apiMocks.getMissionCommand).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('link', { name: 'Trocar missão' }));
    await act(async () => {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(5_000);
    });

    expect(apiMocks.getMissionCommand).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole('button', { name: 'Solicitar armamento' }),
    ).toBeEnabled();
  });
});
