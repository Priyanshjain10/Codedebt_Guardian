import { request } from './client';
import type { SearchResponse } from '@/types/api';

/**
 * Semantic code search via pgvector.
 * NOTE: Backend prefix is /search, NOT /api/v1/search.
 */
export function searchCode(query: string, projectId: string, topK: number = 5) {
    const q = new URLSearchParams({
        q: query,
        project_id: projectId,
        top_k: String(topK),
    });
    return request<SearchResponse>(`/search?${q.toString()}`);
}
