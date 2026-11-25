import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, expect, it, vi } from 'vitest';
import { Px4SitlControls } from '../src/features/missions/Px4SitlControls';
import { SettingsPage } from '../src/features/settings/SettingsPage';
import { PhysicalArmTest } from '../src/features/settings/PhysicalArmTest';
import { SitlArmTest } from '../src/features/settings/SitlArmTest';
import { readyMission, readyVehicle } from './fixtures';

const api = vi.hoisted(() => ({
  commands: vi.fn(),
  request: vi.fn(),
  upload: vi.fn(),
  verifiedMissions: vi.fn(),
}));
const admin = vi.hoisted(() => ({ listVehicles: vi.fn(), getMission: vi.fn() }));
const benchApi = vi.hoisted(() => ({ status: vi.fn(), request: vi.fn() }));
vi.mock('../src/services/real-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services/real-api')>()),
  px4SitlApi: api,
  benchArmApi: benchApi,
}));
vi.mock('../src/services', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services')>()),
  adminApi: admin,
}));

beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  benchApi.status.mockResolvedValue({ enabled: false, target: null, request: null });
});

it('exige confirmação de ARM e apresenta a decisão recebida do PX4', async () => {
  const user = userEvent.setup();
  const mission = { ...readyMission, status: 'VERIFIED' as const, qgroundcontrol_sitl_review_event_id: 'review' };
  const response = {
    id: 'command',
    command: 'ARM',
    status: 'FAILED',
    result_detail: 'Armamento rejeitado pelo veículo: 2',
    requested_at: '2026-01-01T09:00:00Z',
  };
  api.commands.mockResolvedValueOnce([]).mockResolvedValue([response]);
  api.request.mockResolvedValue(response);
  render(<Px4SitlControls mission={mission} vehicle={readyVehicle} onChange={vi.fn()} />);
  await user.click(await screen.findByRole('button', { name: 'Armar drone' }));
  expect(api.request).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Confirmar no SITL' }));
  expect(api.request).toHaveBeenCalledExactlyOnceWith(mission.id, 'ARM');
  expect(await screen.findByText('Armamento rejeitado pelo veículo: 2')).toBeInTheDocument();
  expect(api.upload).not.toHaveBeenCalled();
});

it('mantém o teste desabilitado quando existe apenas hardware real', async () => {
  admin.listVehicles.mockResolvedValue([
    { ...readyVehicle, autopilot_system: 'PX4', operational_source: 'HARDWARE_REAL' },
  ]);
  const user = userEvent.setup();
  render(<><SettingsPage /><SitlArmTest /></>);
  await screen.findByText(/Conecte o PX4 SITL no ambiente de teste/);
  await user.click(screen.getByRole('checkbox', { name: 'Ativar modo bancada' }));
  expect(screen.getByRole('button', { name: 'Armar drone' })).toBeDisabled();
  expect(api.verifiedMissions).not.toHaveBeenCalled();
  expect(api.request).not.toHaveBeenCalled();
});

it('envia somente ARM após selecionar a missão SITL nas configurações e confirmar', async () => {
  const vehicle = { ...readyVehicle, autopilot_system: 'PX4' };
  const mission = {
    ...readyMission,
    status: 'VERIFIED',
    vehicle_id: vehicle.id,
    qgroundcontrol_sitl_review_event_id: 'review',
  };
  const command = {
    id: 'arm-command',
    command: 'ARM',
    status: 'PENDING',
    requested_at: '2026-08-06T12:00:00Z',
  };
  admin.listVehicles.mockResolvedValue([vehicle]);
  api.verifiedMissions.mockResolvedValue([mission]);
  admin.getMission.mockResolvedValue(mission);
  api.commands.mockResolvedValueOnce([]).mockResolvedValue([command]);
  api.request.mockResolvedValue(command);

  const user = userEvent.setup();
  render(<SitlArmTest />);
  await screen.findByRole('option', { name: /Drone de teste/ });
  expect(screen.getByRole('button', { name: 'Armar drone' })).toBeDisabled();

  await user.selectOptions(screen.getByLabelText('Missão verificada no simulador'), mission.id);
  await user.click(screen.getByRole('button', { name: 'Armar drone' }));
  await user.click(screen.getByRole('button', { name: 'Cancelar' }));
  expect(api.request).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: 'Iniciar missão' })).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Armar drone' }));
  await user.click(screen.getByRole('button', { name: 'Confirmar no SITL' }));

  expect(api.request).toHaveBeenCalledExactlyOnceWith(mission.id, 'ARM');
  expect(await screen.findByText('ARM · Solicitação registrada')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Armar drone' })).toBeDisabled();
  expect(api.upload).not.toHaveBeenCalled();
});

it('seleciona a Pixhawk explicitamente e separa timeout de estado observado', async () => {
  admin.listVehicles.mockResolvedValue([]);
  const target = {
    id: 'px4-bench',
    name: 'Pixhawk de bancada',
    session_id: 'bench-session',
    armed: false,
    heartbeat_at: '2026-11-24T12:00:00Z',
  };
  const result = {
    id: 'bench-arm-command',
    vehicle_id: target.id,
    status: 'UNCONFIRMED',
    requested_at: '2026-11-24T12:00:00Z',
    transmitted: true,
    ack_result: null,
    confirmed_heartbeat_at: null,
    detail: 'Timeout aguardando ACK',
  };
  benchApi.status.mockResolvedValue({ enabled: true, target, request: null });
  benchApi.request.mockImplementation(async () => {
    benchApi.status.mockResolvedValue({
      enabled: true, target: { ...target, armed: true }, request: result,
    });
    return result;
  });

  const user = userEvent.setup();
  render(<PhysicalArmTest />);
  await screen.findByRole('option', { name: target.name });
  const arm = screen.getByRole('button', { name: 'Solicitar ARM físico' });
  expect(arm).toBeDisabled();
  await user.selectOptions(screen.getByLabelText('Veículo físico de ensaio'), target.session_id);
  await user.click(arm);
  expect(benchApi.request).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Cancelar' }));
  await user.click(arm);
  await user.click(screen.getByRole('button', { name: 'Confirmar ARM físico' }));
  expect(benchApi.request).toHaveBeenCalledExactlyOnceWith(target);
  expect(await screen.findByText('Sem ACK registrado')).toBeInTheDocument();
  expect(await screen.findByText(/Armada ·/)).toBeInTheDocument();
  expect(screen.getByText('Sem confirmação')).toBeInTheDocument();
});

it('oferece somente a preferência visual nas configurações operacionais', () => {
  render(<SettingsPage />);
  expect(screen.getByRole('checkbox', { name: 'Ativar modo bancada' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /armar|solicitar ARM físico/i })).not.toBeInTheDocument();
  expect(benchApi.status).not.toHaveBeenCalled();
});
