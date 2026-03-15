import { request } from './client';
import type { APIKeyListResponse, CreateAPIKeyResponse } from '@/types/api';

export function listAPIKeys() {
    return request<APIKeyListResponse>('/api/v1/api-keys');
}

export function createAPIKey(label: string) {
    return request<CreateAPIKeyResponse>('/api/v1/api-keys', {
        method: 'POST',
        body: JSON.stringify({ label }),
    });
}

export function revokeAPIKey(id: string) {
    return request<void>(`/api/v1/api-keys/${id}`, { method: 'DELETE' });
}
