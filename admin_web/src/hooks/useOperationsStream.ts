import { useEffect, useRef, useState } from 'react';
import { appConfig } from '../services';
import { sessionToken } from '../services/session';

export type StreamStatus = 'disabled' | 'connecting' | 'connected' | 'reconnecting';

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
    let stopped = false;
    let attempts = 0;

    const connect = () => {
      if (stopped) return;
      setStatus(attempts === 0 ? 'connecting' : 'reconnecting');
      socket = new WebSocket(`${appConfig.wsBaseUrl}/ws/admin/operations`);
      socket.addEventListener('open', () => {
        attempts = 0;
        setStatus('connected');
        const token = sessionToken.get();
        if (token) {
          // O token não vai na URL. O backend pode autenticar o upgrade por cookie
          // HTTP-only ou validar esta primeira mensagem sobre WSS.
          socket?.send(JSON.stringify({ type: 'AUTH', token }));
        }
      });
      socket.addEventListener('message', () => updateRef.current());
      socket.addEventListener('close', () => {
        if (stopped) return;
        attempts += 1;
        setStatus('reconnecting');
        reconnectTimer = window.setTimeout(
          connect,
          Math.min(1000 * 2 ** (attempts - 1), 15_000),
        );
      });
      socket.addEventListener('error', () => socket?.close());
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return status;
}
