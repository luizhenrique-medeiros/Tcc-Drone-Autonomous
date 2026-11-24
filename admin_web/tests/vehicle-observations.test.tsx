import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { OperationsPage } from '../src/features/telemetry/OperationsPage';
import { readyHealth, readyVehicle } from './fixtures';

const api = vi.hoisted(() => ({
  listOrders: vi.fn(),
  listEvents: vi.fn(),
  listVehicles: vi.fn(),
  getVehicleHealth: vi.fn(),
}));

vi.mock('../src/services', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services')>()),
  adminApi: api,
}));
vi.mock('../src/hooks/useOperationsStream', () => ({ useOperationsStream: () => 'connected' }));

it('mostra ACK e waypoint do veículo observado mesmo sem missão vinculada', async () => {
  api.listOrders.mockResolvedValue([]);
  api.listVehicles.mockResolvedValue([readyVehicle]);
  api.getVehicleHealth.mockResolvedValue({ ...readyHealth, armed: true, flight_mode: 'AUTO.MISSION' });
  api.listEvents.mockResolvedValue([
    {
      id: 'ack',
      vehicle_id: readyVehicle.id,
      type: 'MAVLINK_COMMAND_ACK',
      severity: 'INFO',
      message: 'PX4 respondeu ao comando 400 com resultado MAVLink 0.',
      created_at: readyHealth.received_at,
    },
    {
      id: 'waypoint',
      vehicle_id: readyVehicle.id,
      type: 'MAVLINK_MISSION_CURRENT',
      severity: 'INFO',
      message: 'Autopiloto informou waypoint atual 1.',
      created_at: readyHealth.received_at,
    },
    {
      id: 'other',
      vehicle_id: 'other-vehicle',
      type: 'MAVLINK_MISSION_CURRENT',
      severity: 'INFO',
      message: 'Evento de outro veículo.',
      created_at: readyHealth.received_at,
    },
  ]);

  render(<MemoryRouter><OperationsPage /></MemoryRouter>);

  expect(await screen.findByText(/PX4 respondeu ao comando 400/)).toBeInTheDocument();
  expect(screen.getByText('Autopiloto informou waypoint atual 1.')).toBeInTheDocument();
  expect(screen.getByText('AUTO.MISSION')).toBeInTheDocument();
  expect(screen.getByText('Armado')).toBeInTheDocument();
  expect(screen.getByText('Nenhuma missão disponível')).toBeInTheDocument();
  expect(screen.queryByText('Evento de outro veículo.')).not.toBeInTheDocument();
});
