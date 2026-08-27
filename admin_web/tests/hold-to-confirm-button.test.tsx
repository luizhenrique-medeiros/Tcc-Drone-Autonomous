import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HoldToConfirmButton } from '../src/features/missions/HoldToConfirmButton';

describe('confirmação por pressão contínua', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('cancela quando o operador solta antes de dois segundos', () => {
    const confirm = vi.fn();
    render(<HoldToConfirmButton onConfirm={confirm} />);
    const button = screen.getByRole('button', {
      name: 'Segure para solicitar armamento',
    });

    fireEvent.pointerDown(button);
    act(() => vi.advanceTimersByTime(1_999));
    fireEvent.pointerUp(button);
    act(() => vi.advanceTimersByTime(10));

    expect(confirm).not.toHaveBeenCalled();
  });

  it('confirma uma única vez após dois segundos completos', () => {
    const confirm = vi.fn();
    render(<HoldToConfirmButton onConfirm={confirm} />);
    const button = screen.getByRole('button', {
      name: 'Segure para solicitar armamento',
    });

    fireEvent.pointerDown(button);
    act(() => vi.advanceTimersByTime(2_000));
    fireEvent.pointerUp(button);
    act(() => vi.advanceTimersByTime(2_000));

    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it('oferece a mesma barreira pelo teclado e cancela com pointercancel', () => {
    const confirm = vi.fn();
    render(<HoldToConfirmButton onConfirm={confirm} />);
    const button = screen.getByRole('button', {
      name: 'Segure para solicitar armamento',
    });

    fireEvent.pointerDown(button);
    fireEvent.pointerCancel(button);
    act(() => vi.advanceTimersByTime(2_000));
    expect(confirm).not.toHaveBeenCalled();

    fireEvent.keyDown(button, { key: 'Enter' });
    act(() => vi.advanceTimersByTime(2_000));
    fireEvent.keyUp(button, { key: 'Enter' });
    expect(confirm).toHaveBeenCalledTimes(1);
  });
});
