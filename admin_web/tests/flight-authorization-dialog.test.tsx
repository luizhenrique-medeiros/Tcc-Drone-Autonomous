import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { FlightAuthorizationDialog } from '../src/features/missions/FlightAuthorizationDialog';
import type { FlightAuthorizationInput } from '../src/services';
import { readyHealth, readyMission, readyVehicle } from './fixtures';

describe('confirmação reforçada de voo', () => {
  it('exige checklist, operador e frase e bloqueia duplo envio', async () => {
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
          health={readyHealth}
          isSubmitting={loading}
          error=""
          onClose={vi.fn()}
          onSubmit={authorize}
        />
      );
    }

    render(<Harness />);
    const authorizeButton = screen.getByRole('button', {
      name: /Autorizar voo uma única vez/i,
    });
    expect(authorizeButton).toBeDisabled();

    for (const checkbox of screen.getAllByRole('checkbox')) {
      await user.click(checkbox);
    }
    await user.type(
      screen.getByLabelText('Operador responsável presente'),
      'Prof. Operador',
    );
    await user.type(
      screen.getByLabelText(/Para confirmar, digite/i),
      'AUTORIZAR VOO A1234567',
    );
    expect(authorizeButton).toBeEnabled();

    await user.click(authorizeButton);
    expect(submit).toHaveBeenCalledTimes(1);
    expect(authorizeButton).toBeDisabled();
    await user.click(authorizeButton);
    expect(submit).toHaveBeenCalledTimes(1);
    release?.();
  });

  it('bloqueia autorização quando o veículo está armado', () => {
    render(
      <FlightAuthorizationDialog
        open
        mission={readyMission}
        vehicle={readyVehicle}
        health={{ ...readyHealth, armed: true }}
        isSubmitting={false}
        error=""
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByText('Veículo não atende aos requisitos mínimos.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Autorizar voo uma única vez/i })).toBeDisabled();
  });
});
