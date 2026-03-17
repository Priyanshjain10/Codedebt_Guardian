import { request, API_BASE } from './client';
import type { GitHubRepoListResponse } from '@/types/api';

/** Redirect user to GitHub App install page (backend handles redirect). */
export function getInstallUrl(): string {
    return `${API_BASE}/api/v1/github/install`;
}

export function listGitHubRepos() {
    return request<GitHubRepoListResponse>('/api/v1/github/repos');
}

export function syncGitHubRepos() {
    return request<{ synced: number }>('/api/v1/github/sync-repos', { method: 'POST' });
}
