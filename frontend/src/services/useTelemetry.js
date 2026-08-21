import { useQuery } from '@tanstack/react-query';
import api from './api';

export function useTelemetry() {
  return useQuery({
    queryKey: ['telemetry'],
    queryFn: async () => {
      const response = await api.get('/metrics/telemetry');
      return response.data;
    },
    refetchInterval: 60000,
  });
}

export function useKpis() {
  return useQuery({
    queryKey: ['kpis'],
    queryFn: async () => {
      const response = await api.get('/metrics/kpi');
      return response.data;
    },
    refetchInterval: 60000,
  });
}
