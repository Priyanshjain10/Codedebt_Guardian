import { request } from './client';
import type { DebtCategory } from '@/types/api';

export interface AnalyticsStatsResponse {
    scans_run: number;
    total_issues: number;
    fixes_generated: number;
    prs_created: number;
    debt_trend: Array<{
        date: string;
        debt_score: number;
        scan_id: string;
    }>;
    category_breakdown: Record<DebtCategory, number>;
    severity_breakdown: {
        CRITICAL: number;
        HIGH: number;
        MEDIUM: number;
        LOW: number;
    };
}

export function getAnalyticsStats(days: number = 30) {
    return request<AnalyticsStatsResponse>(`/api/v1/analytics/stats?days=${days}`);
}
