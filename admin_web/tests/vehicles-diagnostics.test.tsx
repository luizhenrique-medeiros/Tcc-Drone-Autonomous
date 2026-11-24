import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { VehiclesPage } from '../src/features/vehicles/VehiclesPage';
import { readyHealth, readyVehicle } from './fixtures';

const apiMocks = vi.hoisted(() => ({
  listVehicles: vi.fn(),
  getVehicleHealth: vi.fn(),
}));
const streamMock = vi.hoisted(() => ({
  onUpdate: null as (() => void) | null,
}));

vi.mock('../src/services', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services')>()),
  adminApi: apiMocks,
}));

vi.mock('../src/hooks/useOperationsStream', () => ({
  useOperationsStream: (onUpdate: () => void) => {
    streamMock.onUpdate = onUpdate;
    return 'connected';
  },
}));

describe('diagnóstico de integração do veículo', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    streamMock.onUpdate = null;
    apiMocks.listVehicles.mockResolvedValue([
      {
        ...readyVehicle,
        autopilot_version: 'ArduCopter 4.6',
        gateway_id: 'gateway-real-1',
      },
    ]);
    apiMocks.getVehicleHealth.mockResolvedValue({
      ...readyHealth,
      source: 'HARDWARE_REAL',
      connection_state: 'CONNECTED',
      connection_mode: 'DIRECT',
      connection_topology: 'PIXHAWK_USB_SERIAL',
      connection_endpoint: 'COM7',
      serial_port: 'COM7',
      connection_baud: 57600,
      mavlink_system_id: 1,
      mavlink_component_id: 1,
      heartbeat_age_seconds: 0.4,
      mission_upload_enabled: false,
      flight_commands_enabled: false,
      vehicle_arm_enabled: false,
      mission_start_enabled: false,
    });
  });

  it('mostra leituras do gateway, do veículo e do WebSocket sem aprovar aptidão', async () => {
    render(<VehiclesPage />);

    expect(await screen.findByText('COM7')).toBeInTheDocument();
    expect(screen.getByText('Gateway')).toBeInTheDocument();
    expect(screen.getByText('Pixhawk')).toBeInTheDocument();
    expect(screen.getByText('Autopiloto')).toBeInTheDocument();
    expect(screen.getByText('ArduPilot')).toBeInTheDocument();
    expect(screen.getByText('MAVLink')).toBeInTheDocument();
    expect(screen.getByText(/57600 baud/)).toBeInTheDocument();
    expect(screen.getByText(/SYSID 1/)).toBeInTheDocument();
    expect(screen.queryByText('Armamento remoto')).not.toBeInTheDocument();
    expect(screen.queryByText(/mínimo do backend|a leitura atual possui bloqueios/i)).not.toBeInTheDocument();
    expect(screen.getByText('WebSocket')).toBeInTheDocument();

    act(() => streamMock.onUpdate?.());
    await waitFor(() => expect(apiMocks.getVehicleHealth).toHaveBeenCalledTimes(2));
  });
});
