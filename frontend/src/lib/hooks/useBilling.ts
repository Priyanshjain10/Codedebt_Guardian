'use client';

import { useQuery } from '@tanstack/react-query';
import * as billingApi from '@/lib/api/billing';

export function useBilling() {
    return useQuery({
        queryKey: ['billing', 'usage'],
        queryFn: () => billingApi.getUsage(),
        staleTime: 60_000,
    });
}
