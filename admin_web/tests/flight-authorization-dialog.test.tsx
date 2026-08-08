import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { FlightAuthorizationDialog } from '../src/features/missions/FlightAuthorizationDialog';
import type { FlightAuthorizationInput, VehicleHealth } from '../src/services';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

const renderDialog = (health: VehicleHealth = readyHealth) =>
  render(
    <FlightAuthorizationDialog
      open
      mission={readyMission}
      vehicle={readyVehicle}
      health={health}
      isSubmitting={false}
      error=""
      onClose={vi.fn()}
      onSubmit={vi.fn().mockResolvedValue(undefined)}
    />,
  );

describe('autorização de missão', () => {
  it('remove o campo de frase e mostra exatamente três confirmações humanas', () => {
    renderDialog();

    expect(screen.getByRole('dialog', { name: 'Autorizar esta missão?' })).toBeInTheDocument();
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
    expect(
      screen.getByRole('checkbox', {
        name: /Área e condições de voo livres e controladas/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', {
        name: /Drone, carga e mecanismo inspecionados/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: /Operador pronto para iniciar/i }),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/Para confirmar, digite/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/AUTORIZAR VOO/i)).not.toBeInTheDocument();
  });

  it('mantém o botão bloqueado enquanto faltar uma confirmação humana', async () => {
    const user = userEvent.setup();
    renderDialog();
    const authorizeButton = screen.getByRole('button', { name: 'Autorizar missão' });

    await user.type(
      screen.getByLabelText('Nome do operador responsável'),
      'Prof. Operador',
    );
    await user.click(
      screen.getByRole('checkbox', {
        name: /Área e condições de voo livres e controladas/i,
      }),
    );
    await user.click(
      screen.getByRole('checkbox', {
        name: /Drone, carga e mecanismo inspecionados/i,
      }),
    );

    expect(authorizeButton).toBeDisabled();
    await user.click(
      screen.getByRole('checkbox', { name: /Operador pronto para iniciar/i }),
    );
    expect(authorizeButton).toBeEnabled();
  });

  it('mantém blocker técnico impeditivo mesmo com as confirmações preenchidas', async () => {
    const user = userEvent.setup();
    renderDialog({ ...readyHealth, armed: true });

    for (const checkbox of screen.getAllByRole('checkbox')) {
      await user.click(checkbox);
    }
    await user.type(
      screen.getByLabelText('Nome do operador responsável'),
      'Prof. Operador',
    );

    expect(screen.getByText('veículo não confirmado como desarmado.')).toBeInTheDocument();
    expect(screen.getByText('BLOCKING')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Autorizar missão' })).toBeDisabled();
  });

  it('permite warning, submete os três checks e impede duplo envio', async () => {
    const user = userEvent.setup();
    let release: (() => void) | undefined;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    const submit = vi.fn((input: FlightAuthorizationInput) => {
      void input;
      return pending;
    });

    function Harness() {
      const [loading, setLoading] = useState(false);
      const authorize = async (input: FlightAuthorizationInput) => {
        setLoading(true);
        await submit(input);
        setLoading(false);
      };
      return (
        <FlightAuthorizationDialog
          open
          mission={readyMission}
          vehicle={readyVehicle}
          health={{ ...readyHealth, battery_percent: 45 }}
          isSubmitting={loading}
          error=""
          onClose={vi.fn()}
          onSubmit={authorize}
        />
      );
    }

    render(<Harness />);
    expect(screen.getByText('WARNING')).toBeInTheDocument();
    expect(screen.getByText(/45% · próxima do mínimo de 40%/i)).toBeInTheDocument();

    for (const checkbox of screen.getAllByRole('checkbox')) {
      await user.click(checkbox);
    }
    await user.type(
      screen.getByLabelText('Nome do operador responsável'),
      'Prof. Operador',
    );
    const authorizeButton = screen.getByRole('button', { name: 'Autorizar missão' });
    expect(authorizeButton).toBeEnabled();

    await user.dblClick(authorizeButton);
    expect(submit).toHaveBeenCalledTimes(1);
    expect(submit).toHaveBeenCalledWith({
      vehicle_id: readyVehicle.id,
      operator_name: 'Prof. Operador',
      controlled_area_confirmed: true,
      checklist: {
        area_and_conditions_clear: true,
        aircraft_and_payload_inspected: true,
        operator_ready: true,
      },
    });
    expect(authorizeButton).toBeDisabled();

    release?.();
    await waitFor(() => expect(authorizeButton).toBeEnabled());
  });
});
