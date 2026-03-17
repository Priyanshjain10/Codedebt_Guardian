/* ── Core Domain Models ───────────────────────────────────────────────── */

export interface User {
    id: string;
    email: string;
    name: string;
    avatar_url?: string;
}

export interface Organization {
    id: string;
    name: string;
    slug: string;
    plan: 'free' | 'pro' | 'enterprise';
    settings?: Record<string, unknown>;
    created_at: string;
}

export interface Team {
    id: string;
    name: string;
    slug: string;
    member_count: number;
    created_at: string;
}

export interface Project {
    id: string;
    name: string;
    repo_url: string;
    default_branch: string;
    settings?: Record<string, unknown>;
    scan_count?: number;
    created_at: string;
}

export interface APIKey {
    id: string;
    prefix: string;
    label: string;
    last_used_at: string | null;
    created_at: string;
}

export interface GitHubRepo {
    id: number;
    full_name: string;
    name: string;
    private: boolean;
    language: string | null;
    html_url: string;
    description: string | null;
    default_branch: string;
    pushed_at: string | null;
    stargazers_count: number;
}

export type PlanTier = 'free' | 'pro' | 'enterprise';

export interface BillingUsage {
    plan: PlanTier;
    scans_used: number;
    scans_limit: number;
    period_end: string | null;
}
