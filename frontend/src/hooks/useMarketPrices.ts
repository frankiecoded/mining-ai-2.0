import { ChatAPI } from '../services/api';
import { usePolling } from './usePolling';
import type { MarketPricesResponse } from '../types';

export function useMarketPrices(intervalMs = 60_000) {
  return usePolling<MarketPricesResponse>(() => ChatAPI.fetchMarketPrices(), intervalMs);
}
