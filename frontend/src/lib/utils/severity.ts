import type { DebtSeverity, DebtCategory, EffortLevel, DetectionSource, Priority } from '@/types/api';

/* ── Severity helpers ────────────────────────────────────────────────── */

const SEVERITY_CONFIG: Record<DebtSeverity, { label: string; color: string; bg: string; dot: string }> = {
    CRITICAL: { label: 'Critical', color: 'text-sev-critical', bg: 'bg-sev-critical-bg', dot: 'bg-sev-critical' },
    HIGH: { label: 'High', color: 'text-sev-high', bg: 'bg-sev-high-bg', dot: 'bg-sev-high' },
    MEDIUM: { label: 'Medium', color: 'text-sev-medium', bg: 'bg-sev-medium-bg', dot: 'bg-sev-medium' },
    LOW: { label: 'Low', color: 'text-sev-low', bg: 'bg-sev-low-bg', dot: 'bg-sev-low' },
};

export function getSeverityConfig(severity: DebtSeverity) {
    return SEVERITY_CONFIG[severity] ?? SEVERITY_CONFIG.LOW;
}

/* ── Category helpers ────────────────────────────────────────────────── */

const CATEGORY_ICONS: Record<DebtCategory, string> = {
    security: '🔒',
    performance: '⚡',
    maintainability: '🔧',
    complexity: '🧩',
    documentation: '📄',
    testing: '🧪',
    dependencies: '📦',
};

const CATEGORY_COLORS: Record<DebtCategory, string> = {
    security: 'text-sev-critical',
    performance: 'text-accent-amber',
    maintainability: 'text-accent-cyan',
    complexity: 'text-accent-violet',
    documentation: 'text-text-2',
    testing: 'text-brand',
    dependencies: 'text-sev-high',
};

export function getCategoryIcon(category: DebtCategory): string {
    return CATEGORY_ICONS[category] ?? '📋';
}

export function getCategoryColor(category: DebtCategory): string {
    return CATEGORY_COLORS[category] ?? 'text-text-2';
}

/* ── Effort helpers ──────────────────────────────────────────────────── */

export function getEffortLabel(effort: EffortLevel): string {
    switch (effort) {
        case 'MINUTES': return '< 30 min';
        case 'HOURS': return '1–4 hours';
        case 'DAYS': return '1–3 days';
        default: return effort;
    }
}

/* ── Source helpers ───────────────────────────────────────────────────── */

export function getSourceLabel(source: DetectionSource): string {
    switch (source) {
        case 'gemini_ai': return '✦ AI';
        case 'static_analysis': return '📐 Static';
        case 'dependency_analysis': return '📦 Dependency';
        case 'documentation_analysis': return '📄 Docs';
        case 'satd_analysis': return '💬 SATD';
        case 'template': return '📋 Template';
        case 'fallback': return '🔄 Fallback';
        default: return source;
    }
}

/* ── Score color ──────────────────────────────────────────────────────── */

export function getScoreColor(score: number): string {
    if (score >= 81) return 'text-sev-critical';
    if (score >= 61) return 'text-sev-high';
    if (score >= 31) return 'text-sev-medium';
    return 'text-sev-low';
}

export function getGradeColor(grade: string): string {
    switch (grade) {
        case 'A': return 'text-sev-low';
        case 'B': return 'text-brand';
        case 'C': return 'text-sev-medium';
        case 'D': return 'text-sev-high';
        case 'F': return 'text-sev-critical';
        default: return 'text-text-2';
    }
}
