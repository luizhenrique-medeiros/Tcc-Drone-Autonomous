import { useCallback, useEffect, useState } from 'react';
import { getErrorMessage } from '../services';

export interface AsyncData<T> {
  data: T | null;
  isLoading: boolean;
  error: string;
  reload: () => Promise<void>;
  setData: (data: T) => void;
}

export function useAsyncData<T>(loader: () => Promise<T>): AsyncData<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      setData(await loader());
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setIsLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, isLoading, error, reload, setData };
}
