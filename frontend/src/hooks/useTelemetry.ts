import { ChatAPI } from '../services/api';
import { usePolling } from './usePolling';
import type { SystemTelemetry } from '../types';

export function useTelemetry(intervalMs = 10_000) {
  return usePolling<SystemTelemetry>(
    async () => (await ChatAPI.fetchTelemetry()) as unknown as SystemTelemetry,
    intervalMs,
  );
}
