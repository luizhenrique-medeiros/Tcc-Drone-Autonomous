import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useOperationsStream } from '../src/hooks/useOperationsStream';

type Listener = (event: Event) => void;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  readonly listeners = new Map<string, Listener[]>();
  readonly sent: string[] = [];

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.emit('close');
  }

  emit(type: string) {
    for (const listener of this.listeners.get(type) ?? []) listener(new Event(type));
  }
}

describe('reconexão da operação ao vivo', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('autentica fora da URL, recebe atualização e reconecta com backoff', () => {
    sessionStorage.setItem('devcore.admin.token', 'jwt-test');
    const onUpdate = vi.fn();
    const { result, unmount } = renderHook(() => useOperationsStream(onUpdate));
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).not.toContain('token=');

    act(() => FakeWebSocket.instances[0].emit('open'));
    expect(result.current).toBe('connected');
    expect(JSON.parse(FakeWebSocket.instances[0].sent[0])).toEqual({
      type: 'AUTH',
      token: 'jwt-test',
    });

    act(() => FakeWebSocket.instances[0].emit('message'));
    expect(onUpdate).toHaveBeenCalledTimes(1);
    act(() => FakeWebSocket.instances[0].emit('close'));
    expect(result.current).toBe('reconnecting');
    act(() => vi.advanceTimersByTime(1000));
    expect(FakeWebSocket.instances).toHaveLength(2);
    unmount();
  });
});
