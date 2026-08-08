import { useEffect, useRef, useState } from 'react';
import { appConfig } from '../services';
import { sessionToken } from '../services/session';

export type StreamStatus =
  | 'disabled'
  | 'connecting'
  | 'authenticating'
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

const MAX_RECONNECT_ATTEMPTS = 8;
const MAX_RECONNECT_DELAY_MS = 15_000;
const AUTH_TIMEOUT_MS = 5_000;
const UPDATE_COALESCE_MS = 250;

export function useOperationsStream(onUpdate: () => void) {
  const [status, setStatus] = useState<StreamStatus>(
    appConfig.demoMode ? 'disabled' : 'connecting',
  );
  const updateRef = useRef(onUpdate);
  updateRef.current = onUpdate;

  useEffect(() => {
    if (appConfig.demoMode) return undefined;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let authTimer: number | undefined;
    let updateTimer: number | undefined;
    let stopped = false;
    let attempts = 0;

    const clearSocketTimers = () => {
      if (authTimer) window.clearTimeout(authTimer);
      authTimer = undefined;
    };

    const scheduleUpdate = () => {
      if (updateTimer) return;
      updateTimer = window.setTimeout(() => {
        updateTimer = undefined;
        updateRef.current();
      }, UPDATE_COALESCE_MS);
    };

    const connect = () => {
      if (stopped) return;
      const token = sessionToken.get();
      if (!token) {
        setStatus('disconnected');
        return;
      }
      setStatus(attempts === 0 ? 'connecting' : 'reconnecting');
      socket = new WebSocket(`${appConfig.wsBaseUrl}/ws/admin/operations`);
      socket.addEventListener('open', () => {
        setStatus('authenticating');
        // O token não vai na URL; a sessão só é considerada conectada após ACK.
        socket?.send(JSON.stringify({ type: 'AUTH', token }));
        authTimer = window.setTimeout(() => socket?.close(), AUTH_TIMEOUT_MS);
      });
      socket.addEventListener('message', (event) => {
        let type = '';
        try {
          type = (JSON.parse(String(event.data)) as { type?: string }).type ?? '';
        } catch {
          return;
        }
        if (type === 'operations.connected') {
          clearSocketTimers();
          attempts = 0;
          setStatus('connected');
          scheduleUpdate();
          return;
        }
        if (type) scheduleUpdate();
      });
      socket.addEventListener('close', () => {
        clearSocketTimers();
        if (stopped) return;
        attempts += 1;
        if (attempts > MAX_RECONNECT_ATTEMPTS) {
          setStatus('disconnected');
          return;
        }
        setStatus('reconnecting');
        reconnectTimer = window.setTimeout(
          connect,
          Math.min(1000 * 2 ** (attempts - 1), MAX_RECONNECT_DELAY_MS),
        );
      });
      socket.addEventListener('error', () => socket?.close());
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (updateTimer) window.clearTimeout(updateTimer);
      clearSocketTimers();
      socket?.close();
    };
  }, []);

  return status;
}
