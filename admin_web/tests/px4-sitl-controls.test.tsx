import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { Px4SitlControls } from '../src/features/missions/Px4SitlControls';
import { readyMission, readyVehicle } from './fixtures';

const api = vi.hoisted(() => ({ commands: vi.fn(), request: vi.fn(), upload: vi.fn() }));
vi.mock('../src/services/real-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../src/services/real-api')>()),
  px4SitlApi: api,
}));

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
