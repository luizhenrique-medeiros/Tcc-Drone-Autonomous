import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAsyncData } from '../src/hooks/useAsyncData';

describe('concorrência de carregamento', () => {
  it('não deixa uma resposta antiga sobrescrever a mais recente', async () => {
    const resolvers: Array<(value: string) => void> = [];
    const loader = vi.fn(() => new Promise<string>((resolve) => resolvers.push(resolve)));
    const { result } = renderHook(() => useAsyncData(loader));

    expect(resolvers).toHaveLength(1);
    act(() => void result.current.reload());
    expect(resolvers).toHaveLength(2);

    await act(async () => resolvers[1]('mais recente'));
    expect(result.current.data).toBe('mais recente');

    await act(async () => resolvers[0]('antiga'));
    expect(result.current.data).toBe('mais recente');
  });
});
