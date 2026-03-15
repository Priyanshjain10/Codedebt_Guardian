/* ── Scan Domain Types ────────────────────────────────────────────────── */

export type DebtSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type DebtCategory =
    | 'security'
    | 'performance'
    | 'maintainability'
    | 'complexity'
    | 'documentation'
    | 'testing'
    | 'dependencies';
export type EffortLevel = 'MINUTES' | 'HOURS' | 'DAYS';
export type Priority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type DetectionSource =
    | 'static_analysis'
    | 'gemini_ai'
    | 'dependency_analysis'
    | 'documentation_analysis'
    | 'satd_analysis'
    | 'template'
    | 'fallback';

export interface IssueLocation {
    file_path: string;
    line_start: number | null;
    line_end: number | null;
    function_name?: string;
    class_name?: string;
}

export interface RankedIssue {
    id: string;
    type: string;
    title: string;
    description: string;
    category: DebtCategory;
    severity: DebtSeverity;
    location: IssueLocation;
    impact: string;
    effort_to_fix: EffortLevel;
    code_snippet?: string;
    source: DetectionSource;
    confidence: number;
    score: number;
    priority: Priority;
    rank: number;
    quick_win: boolean;
    blocks_other_work: boolean;
    business_justification: string;
    recommended_sprint: 1 | 2 | 3;
}

export interface FixProposal {
    id: string;
    issue_type: string;
    problem_summary: string;
    fix_summary: string;
    before_code: string;
    after_code: string;
    steps: string[];
    source: 'ai' | 'template' | 'fallback';
}

export interface Hotspot {
    file_path: string;
    issue_count: number;
    severity_score: number;
    categories: string[];
}

export interface TDR {
    ratio: number;
    total_debt_minutes: number;
    total_work_minutes: number;
    rating: 'Excellent' | 'Good' | 'Moderate' | 'High' | 'Critical';
}

export interface ScanSummary {
    total_issues: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    fixes_proposed: number;
    grade: 'A' | 'B' | 'C' | 'D' | 'F';
    debt_score: number;
    tokens_input?: number;
    tokens_output?: number;
    model_usage?: Record<string, number>;
}

export type ScanStatus = 'queued' | 'running' | 'completed' | 'failed';
export type ScanType = 'full' | 'pr';

export interface Scan {
    id: string;
    status: ScanStatus;
    repo_url: string;
    branch: string;
    scan_type: ScanType;
    pr_number: number | null;
    debt_score: number;
    summary: ScanSummary;
    detection_results: Record<string, unknown>;
    ranked_issues: RankedIssue[];
    fix_proposals: FixProposal[];
    hotspots: Hotspot[];
    tdr: TDR | null;
    duration_seconds: number | null;
    created_at: string;
    completed_at: string | null;
}

/* ── WebSocket Message Types ─────────────────────────────────────────── */

export type WSProgressStage = 'detection' | 'ranking' | 'fixing' | 'autopilot';

export interface WSConnected {
    type: 'connected';
    scan_id: string;
}

export interface WSProgress {
    type: 'progress';
    stage: WSProgressStage;
    pct: number;
    message: string;
}

export interface WSCompleted {
    type: 'completed';
    scan_id: string;
    summary: ScanSummary;
}

export interface WSError {
    type: 'error';
    message: string;
}

export interface WSHeartbeat {
    type: 'heartbeat';
}

export type WSScanMessage = WSConnected | WSProgress | WSCompleted | WSError | WSHeartbeat;

export interface WSDashboardScanStarted {
    type: 'scan.started';
    scan_id: string;
    project_id: string;
}

export interface WSDashboardScanCompleted {
    type: 'scan.completed';
    scan_id: string;
    debt_score: number;
    summary: ScanSummary;
}

export interface WSDashboardPRCreated {
    type: 'pr.created';
    pr_url: string;
    scan_id: string;
    title: string;
}

export type WSDashboardMessage =
    | WSDashboardScanStarted
    | WSDashboardScanCompleted
    | WSDashboardPRCreated
    | WSHeartbeat;
