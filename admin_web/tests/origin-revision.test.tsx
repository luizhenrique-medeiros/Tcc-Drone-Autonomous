import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { OriginRevisionDialog } from '../src/features/missions/OriginRevisionDialog';
import { canReviseOrigin } from '../src/features/missions/origin-revision-readiness';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const mission = { ...readyMission, status: 'VERIFIED' as const, vehicle_id: readyVehicle.id, file_hash: 'a'.repeat(64) };
const health = { ...readyHealth, vehicle_id: readyVehicle.id, flight_mode: 'STABILIZE', armed: false,
  source: 'HARDWARE_REAL' as const, mission_upload_enabled: false, flight_commands_enabled: false,
  mission_start_enabled: false, vehicle_arm_enabled: false, current_latitude: -23.1186, current_longitude: -46.5812 };

describe('revisão explícita da origem', () => {
  it('exige observação, desarmado, fonte conhecida e versão não executada', () => {
    expect(canReviseOrigin(mission, health)).toBe(true);
    for (const update of [{ armed: true }, { is_stale: true }, { vehicle_arm_enabled: true },
      { mission_upload_enabled: null }, { vehicle_id: 'other' }, { flight_mode: 'AUTO' }]) {
      expect(canReviseOrigin(mission, { ...health, ...update })).toBe(false);
    }
    expect(canReviseOrigin({ ...mission, status: 'EXECUTING' }, health)).toBe(false);
  });
  it('não envia destino e exige confirmação nova após editar coordenadas', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<OriginRevisionDialog open mission={mission} health={health} busy={false} error=""
      onClose={vi.fn()} onSubmit={onSubmit} />);
    const submit = screen.getByRole('button', { name: 'Gerar nova versão' });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Motivo da mudança de origem'), { target: { value: 'Reposicionado pelo operador Luiz' } });
    fireEvent.click(screen.getByRole('checkbox'));
    expect(submit).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Latitude da nova origem'), { target: { value: '-23.11861' } });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(submit);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit).toHaveBeenCalledWith({ expected_version: mission.version, expected_sha256: mission.file_hash,
      origin_latitude: '-23.1186100', origin_longitude: '-46.5812000', reason: 'Reposicionado pelo operador Luiz', position_confirmed: true });
  });
});
