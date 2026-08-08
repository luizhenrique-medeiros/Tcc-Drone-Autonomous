import { useCallback, useEffect, useRef, useState } from 'react';
import { getErrorMessage } from '../services';

export interface AsyncData<T> {
  data: T | null;
  isLoading: boolean;
  error: string;
  lastSuccessAt: string | null;
  reload: () => Promise<void>;
  setData: (data: T) => void;
}

export function useAsyncData<T>(loader: () => Promise<T>): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastSuccessAt, setLastSuccessAt] = useState<string | null>(null);
  const requestSequence = useRef(0);

  const reload = useCallback(async () => {
    const sequence = ++requestSequence.current;
    setIsLoading(true);
    setError('');
    try {
      const nextData = await loader();
      if (sequence !== requestSequence.current) return;
      setData(nextData);
      setLastSuccessAt(new Date().toISOString());
    } catch (loadError) {
      if (sequence !== requestSequence.current) return;
      setError(getErrorMessage(loadError));
    } finally {
      if (sequence === requestSequence.current) setIsLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
    return () => {
      requestSequence.current += 1;
    };
  }, [reload]);

  return { data, isLoading, error, lastSuccessAt, reload, setData };
}
