/* ── API Response Wrappers ────────────────────────────────────────────── */

import type { Scan, ScanSummary } from './scan';
import type { User, Organization, Team, Project, APIKey, GitHubRepo, BillingUsage } from './models';

/* Auth */
export interface AuthTokens {
    access_token: string;
    refresh_token: string;
}

/* Scans */
export interface CreateScanResponse {
    scan_id: string;
    status: string;
    ws_url: string;
}

export interface ScanListResponse {
    scans: Scan[];
    total: number;
}

export interface CreateFixPRResponse {
    status: string;
    pr_url: string;
    pr_number: number;
    title: string;
}

export interface ScanListParams {
    limit?: number;
    offset?: number;
    status?: string;
}

/* Projects */
export interface ProjectListResponse {
    projects: Project[];
}

/* Organizations */
export interface OrganizationListResponse {
    organizations: Organization[];
}

export interface TeamListResponse {
    teams: Team[];
}

/* API Keys */
export interface APIKeyListResponse {
    api_keys: APIKey[];
}

export interface CreateAPIKeyResponse {
    id: string;
    key: string;
    prefix: string;
    label: string;
    message: string;
}

/* GitHub */
export interface GitHubRepoListResponse {
    repos: GitHubRepo[];
}

/* Billing */
export interface CheckoutResponse {
    checkout_url: string;
}

/* Search */
export interface SearchResult {
    file_path: string;
    content: string;
    start_line: number;
    end_line: number;
    score: number;
}

export interface SearchResponse {
    query: string;
    project_id: string;
    results: SearchResult[];
}

/* Re-exports */
export type { Scan, ScanSummary, User, Organization, Team, Project, APIKey, GitHubRepo, BillingUsage };
export type {
    RankedIssue,
    FixProposal,
    Hotspot,
    TDR,
    DebtSeverity,
    DebtCategory,
    EffortLevel,
    Priority,
    DetectionSource,
    ScanStatus,
    WSScanMessage,
    WSDashboardMessage,
    WSProgressStage,
} from './scan';
export type { PlanTier } from './models';
