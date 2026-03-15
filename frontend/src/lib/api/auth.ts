import { request } from './client';
import type { AuthTokens, User } from '@/types/api';

export function register(data: { email: string; password: string; name: string }) {
    return request<AuthTokens>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function login(data: { email: string; password: string }) {
    return request<AuthTokens>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

// token param allows calling getMe immediately after login/register
// before the token is stored in localStorage
export function getMe(token?: string) {
    return request<User>('/api/v1/auth/me', {}, token);
}