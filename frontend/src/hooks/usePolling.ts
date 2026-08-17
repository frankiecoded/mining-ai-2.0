import { useCallback, useEffect, useRef, useState } from 'react';

interface PollingState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

/**
 * Generic data-fetching hook with optional polling.
 * Shared by telemetry / market / task panels to avoid duplication.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number | null,
): PollingState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refresh = useCallback(async () => {
    try {
      setError(null);
      setData(await fetcherRef.current());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      if (!active) return;
      setLoading(true);
      try {
        setData(await fetcherRef.current());
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Connection failed');
      } finally {
        if (active) setLoading(false);
      }
    })();

    const id = intervalMs ? window.setInterval(() => {
      void fetcherRef.current()
        .then((d) => { setData(d); setError(null); })
        .catch((e) => setError(e instanceof Error ? e.message : 'Connection failed'));
    }, intervalMs) : null;

    return () => {
      active = false;
      if (id) window.clearInterval(id);
    };
  }, [intervalMs]);

  return { data, error, loading, refresh };
}
