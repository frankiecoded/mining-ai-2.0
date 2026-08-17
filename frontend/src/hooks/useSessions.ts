import { useCallback, useEffect, useState } from 'react';
import { ChatAPI } from '../services/api';
import type { ChatSession } from '../types';

export function useSessions(refreshKey?: unknown) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      setSessions((await ChatAPI.fetchSessions()).sessions ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  return { sessions, loading, error, refresh };
}
