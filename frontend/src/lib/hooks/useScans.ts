'use client';

import { useQuery } from '@tanstack/react-query';
import * as scansApi from '@/lib/api/scans';
import type { ScanListParams } from '@/types/api';

export const scanKeys = {
    all: ['scans'] as const,
    list: (p: ScanListParams) => ['scans', 'list', p] as const,
    detail: (id: string) => ['scans', id] as const,
    latest: () => ['scans', 'latest'] as const,
};

export function useScans(params: ScanListParams = {}) {
    return useQuery({
        queryKey: scanKeys.list(params),
        queryFn: () => scansApi.listScans(params),
        staleTime: 10_000,
    });
}

export function useScan(id: string) {
    return useQuery({
        queryKey: scanKeys.detail(id),
        queryFn: () => scansApi.getScan(id),
        enabled: !!id,
        refetchInterval: (query) => {
            const data = query.state.data;
            return data?.status === 'completed' || data?.status === 'failed' ? false : 5_000;
        },
    });
}

export function useLatestScan() {
    return useQuery({
        queryKey: scanKeys.latest(),
        queryFn: () => scansApi.getLatestScan(),
        retry: false, // Don't retry on 404
        staleTime: 30_000,
    });
}
