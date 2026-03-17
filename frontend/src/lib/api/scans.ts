import { request } from './client';
import type {
    Scan,
    CreateScanResponse,
    ScanListResponse,
    ScanListParams,
    CreateFixPRResponse,
} from '@/types/api';

export function createScan(data: {
    repo_url: string;
    branch?: string;
    project_id?: string;
    auto_fix?: boolean;
    max_prs?: number;
}) {
    return request<CreateScanResponse>('/api/v1/scans', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export function listScans(params: ScanListParams = {}) {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', String(params.limit));
    if (params.offset) q.set('offset', String(params.offset));
    if (params.status) q.set('status', params.status);
    return request<ScanListResponse>(`/api/v1/scans?${q.toString()}`);
}

export function getScan(id: string) {
    return request<Scan>(`/api/v1/scans/${id}`);
}

export function getLatestScan() {
    return request<Scan>('/api/v1/scans/latest');
}

export function createFixPR(scanId: string, fixIndex: number) {
    return request<CreateFixPRResponse>(`/api/v1/scans/${scanId}/fix/${fixIndex}`, {
        method: 'POST',
    });
}

export function getScanReportUrl(scanId: string, format: 'html' | 'pdf' = 'html'): string {
    const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return `${base}/api/v1/scans/${scanId}/report?format=${format}`;
}

export interface PullRequest {
    id: string;
    scan_id: string;
    title: string;
    pr_url: string;
    pr_number: number;
    status: string;
    created_at: string;
}

export function getPullRequests() {
    return request<PullRequest[]>('/api/v1/scans/pull-requests');
}
