import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ArmVehicleDialog } from '../src/features/missions/ArmVehicleDialog';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const renderDialog = (overrides: { blockers?: string[] } = {}) => {
  const submit = vi.fn().mockResolvedValue(undefined);
  render(
    <ArmVehicleDialog
      open
      mission={{ ...readyMission, status: 'VERIFIED' }}
      vehicle={readyVehicle}
      health={{
        ...readyHealth,
        flight_commands_enabled: true,
        vehicle_arm_enabled: true,
      }}
      blockers={overrides.blockers ?? []}
      isSubmitting={false}
      error=""
      onClose={vi.fn()}
      onSubmit={submit}
    />,
  );
  return submit;
};

describe('diálogo de solicitação de armamento', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('exige justificativa, três confirmações independentes e hold completo', async () => {
    const submit = renderDialog();
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);

    const holdButton = screen.getByRole('button', {
      name: 'Segure para solicitar armamento',
    });
    expect(holdButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Justificativa operacional'), {
      target: { value: 'Armamento presencial da missão verificada' },
    });
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /Área ao redor do veículo livre e controlada/i,
      }),
    );
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /Operador presente junto ao veículo/i,
      }),
    );
    expect(holdButton).toBeDisabled();
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: /Safety switch pronto para uso/i,
      }),
    );
    expect(holdButton).toBeEnabled();

    fireEvent.pointerDown(holdButton);
    await act(async () => {
      vi.advanceTimersByTime(2_000);
      await Promise.resolve();
    });

    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith({
      reason: 'Armamento presencial da missão verificada',
      area_clear_confirmed: true,
      operator_present_confirmed: true,
      safety_switch_ready_confirmed: true,
    });
  });

  it('mantém o hold bloqueado quando existe blocker técnico', () => {
    renderDialog({ blockers: ['Heartbeat ausente.'] });

    expect(screen.getByText('Heartbeat ausente.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Segure para solicitar armamento' }),
    ).toBeDisabled();
  });
});
