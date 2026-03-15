'use client';

import { useQuery } from '@tanstack/react-query';
import * as projectsApi from '@/lib/api/projects';

export const projectKeys = {
    all: ['projects'] as const,
    detail: (id: string) => ['projects', id] as const,
};

export function useProjects() {
    return useQuery({
        queryKey: projectKeys.all,
        queryFn: () => projectsApi.listProjects(),
    });
}

export function useProject(id: string) {
    return useQuery({
        queryKey: projectKeys.detail(id),
        queryFn: () => projectsApi.getProject(id),
        enabled: !!id,
    });
}
