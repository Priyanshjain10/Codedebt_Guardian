import { request } from './client';
import type { Project, ProjectListResponse } from '@/types/api';

export function createProject(data: { name: string; repo_url: string; default_branch?: string; team_id?: string }) {
    return request<Project>('/api/v1/projects', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function listProjects(params: { limit?: number; offset?: number } = {}) {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    return request<ProjectListResponse>(`/api/v1/projects?${q.toString()}`);
}

export function getProject(id: string) {
    return request<Project>(`/api/v1/projects/${id}`);
}

export function deleteProject(id: string) {
    return request<void>(`/api/v1/projects/${id}`, { method: 'DELETE' });
}
