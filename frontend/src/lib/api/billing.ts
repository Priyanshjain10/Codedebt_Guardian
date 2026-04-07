import { request } from './client';
import type { BillingUsage, CheckoutResponse } from '@/types/api';

export function getUsage() {
    return request<BillingUsage>('/api/v1/billing/usage');
}

export function createCheckout(plan: string, orgId?: string) {
    return request<CheckoutResponse>('/api/v1/billing/checkout', {
        method: 'POST',
        body: JSON.stringify({ plan, ...(orgId ? { org_id: orgId } : {}) }),
    });
}
