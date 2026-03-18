'use client';

import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
    Shield,
    AlertTriangle,
    Wrench,
    Activity,
    ScanSearch,
    BarChart3,
    Zap,
    Plus,
    ExternalLink,
    ChevronRight,
    ArrowUpRight,
    GitPullRequest,
    Eye,
} from 'lucide-react';
import { MetricCard } from '@/components/ui/MetricCard';
import { DebtScoreRing } from '@/components/ui/DebtScoreRing';
import { SeverityBadge } from '@/components/ui/SeverityBadge';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { SkeletonCard, SkeletonTable } from '@/components/ui/SkeletonCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { useScans } from '@/lib/hooks/useScans';
import { useAuthStore } from '@/store/authStore';
import { useDashboardWS } from '@/lib/hooks/useDashboardWS';
import { request } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { relativeTime } from '@/lib/utils/formatters';
import { cn } from '@/lib/utils/cn';
import type { Scan, RankedIssue, Hotspot } from '@/types/api';
import Link from 'next/link';

const pageVariants = {
    initial: { opacity: 0, y: 6 },
    animate: { opacity: 1, y: 0, transition: { duration: 0.18, ease: 'easeOut' } },
};

/* ── Pipeline Visualization ──────────────────────────────────────────── */

const PIPELINE_STAGES = [
    { id: 'repo', label: 'Repository', icon: '📁', color: 'text-text-2' },
    { id: 'detection', label: 'Detection', icon: '🔍', color: 'text-accent-cyan' },
    { id: 'ranking', label: 'Prioritization', icon: '📊', color: 'text-accent-violet' },
    { id: 'fixes', label: 'Fixes', icon: '🔧', color: 'text-brand' },
    { id: 'pr', label: 'Pull Requests', icon: '🔀', color: 'text-accent-amber' },
] as const;

function ScanPipelineViz({ latestScan }: { latestScan: Scan | null }) {
    const router = useRouter();

    const getStageStat = (stageId: string): string => {
        if (!latestScan?.summary) return '—';
        const s = latestScan.summary;
        switch (stageId) {
            case 'repo': return (latestScan.repo_url ?? '').split('/').slice(-1)[0] || 'Repo';
            case 'detection': return `${s.total_issues ?? 0} issues`;
            case 'ranking': return `${s.critical ?? 0} critical`;
            case 'fixes': return `${s.fixes_proposed ?? 0} fixes`;
            case 'pr': return 'Ready';
            default: return '—';
        }
    };

    return (
        <div className="bg-bg-card border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-text-1">Scan Pipeline</h2>
                <Link href="/scans/new" className="text-xs text-brand hover:text-brand-light transition-colors flex items-center gap-1">
                    Run Scan <ChevronRight className="w-3 h-3" />
                </Link>
            </div>
            <div className="flex items-center gap-1">
                {PIPELINE_STAGES.map((stage, i) => (
                    <div key={stage.id} className="flex items-center flex-1 min-w-0">
                        <motion.button
                            whileHover={{ y: -1 }}
                            onClick={() => {
                                if (latestScan) {
                                    if (stage.id === 'detection') router.push(`/scans/${latestScan.id}/issues`);
                                    else if (stage.id === 'fixes') router.push(`/scans/${latestScan.id}/fixes`);
                                    else router.push(`/scans/${latestScan.id}`);
                                }
                            }}
                            className="flex-1 bg-bg-card-2 border border-border rounded-lg p-3 hover:border-brand/30 transition-colors text-left"
                        >
                            <span className="text-lg mb-1 block">{stage.icon}</span>
                            <p className={cn('text-xs font-medium', stage.color)}>{stage.label}</p>
                            <p className="text-[10px] text-text-3 mt-0.5 truncate">{getStageStat(stage.id)}</p>
                        </motion.button>
                        {i < PIPELINE_STAGES.length - 1 && (
                            <ChevronRight className="w-4 h-4 text-text-3 shrink-0 mx-0.5" />
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

/* ── Debt Heatmap ────────────────────────────────────────────────────── */

function DebtHeatmap({ hotspots }: { hotspots: Hotspot[] }) {
    const sorted = [...(hotspots || [])].sort((a, b) => b.severity_score - a.severity_score).slice(0, 30);

    const getColor = (score: number): string => {
        if (score >= 80) return 'bg-sev-critical/60';
        if (score >= 60) return 'bg-sev-high/50';
        if (score >= 30) return 'bg-sev-medium/40';
        return 'bg-sev-low/30';
    };

    if (!sorted.length) {
        return (
            <div className="bg-bg-card border border-border rounded-xl p-4">
                <h3 className="text-xs font-semibold text-text-2 mb-3">Technical Debt Heatmap</h3>
                <p className="text-xs text-text-3 text-center py-6">No hotspot data yet</p>
            </div>
        );
    }

    return (
        <div className="bg-bg-card border border-border rounded-xl p-4">
            <h3 className="text-xs font-semibold text-text-2 mb-3">Technical Debt Heatmap</h3>
            <div className="grid grid-cols-6 gap-1">
                {sorted.map((h, i) => {
                    const size = Math.max(1, Math.min(3, Math.ceil(h.issue_count / 3)));
                    return (
                        <div
                            key={i}
                            className={cn(
                                'rounded cursor-pointer transition-transform hover:scale-110 relative group',
                                getColor(h.severity_score),
                            )}
                            style={{
                                gridColumn: `span ${Math.min(size, 2)}`,
                                height: `${20 + size * 8}px`,
                            }}
                            title={`${h.file_path} — ${h.issue_count} issues`}
                        >
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 bg-bg-card border border-border rounded px-2 py-1 text-[10px] text-text-1 whitespace-nowrap opacity-0 group-hover:opacity-100 z-10 pointer-events-none transition-opacity shadow-lg">
                                <p className="font-mono text-text-code">{(h.file_path ?? '').split('/').pop()}</p>
                                <p className="text-text-3">{h.issue_count} issues</p>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

/* ── AI Insights Panel ───────────────────────────────────────────────── */

function AIInsightsPanel({ scan }: { scan: Scan | null }) {
    const router = useRouter();
    const issues = scan?.ranked_issues ?? [];

    const insights = [
        {
            icon: '🔴',
            count: issues.filter((i) => i.category === 'security').length,
            label: 'Security vulnerabilities found',
            action: 'Review',
            filter: 'category=security',
        },
        {
            icon: '⚠️',
            count: issues.filter((i) => i.category === 'maintainability').length,
            label: 'Code smells can be refactored',
            action: 'Optimize',
            filter: 'category=maintainability',
        },
        {
            icon: '⚡',
            count: issues.filter((i) => i.quick_win).length,
            label: 'Quick wins available',
            action: 'Fix Now',
            filter: 'quick_win=true',
        },
        {
            icon: '📦',
            count: issues.filter((i) => i.category === 'dependencies').length,
            label: 'Dependency issues detected',
            action: 'Update',
            filter: 'category=dependencies',
        },
    ];

    return (
        <div className="bg-bg-card border border-border rounded-xl p-4">
            <h3 className="text-xs font-semibold text-text-2 mb-3">AI Insights</h3>
            <div className="space-y-2">
                {insights.map((insight) => (
                    <button
                        key={insight.filter}
                        onClick={() => scan && router.push(`/scans/${scan.id}/issues?${insight.filter}`)}
                        className="flex items-center w-full gap-3 h-9 px-2 rounded-lg text-left hover:bg-bg-card-2 transition-colors group"
                    >
                        <span className="text-sm">{insight.icon}</span>
                        <span className="text-xs font-mono font-bold text-text-1 w-6">{insight.count}</span>
                        <span className="text-xs text-text-2 flex-1 truncate">{insight.label}</span>
                        <span className="text-[10px] font-medium text-brand opacity-0 group-hover:opacity-100 transition-opacity">
                            {insight.action} →
                        </span>
                    </button>
                ))}
            </div>
        </div>
    );
}

/* ── Recent Scans Table ──────────────────────────────────────────────── */

function RecentScansTable({ scans }: { scans: Scan[] }) {
    const router = useRouter();

    if (!scans.length) {
        return (
            <div className="bg-bg-card border border-border rounded-xl p-4">
                <h3 className="text-xs font-semibold text-text-2 mb-3">Recent Scans</h3>
                <EmptyState
                    icon={ScanSearch}
                    title="No scans yet"
                    description="Run your first scan to see results here"
                    action={{ label: 'Run Scan', onClick: () => router.push('/scans/new') }}
                />
            </div>
        );
    }

    return (
        <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <h3 className="text-xs font-semibold text-text-2">Recent Scans</h3>
                <Link href="/scans" className="text-[10px] text-brand hover:text-brand-light transition-colors">
                    View all →
                </Link>
            </div>
            <div className="divide-y divide-border">
                {scans.slice(0, 5).map((scan) => (
                    <Link
                        key={scan.id}
                        href={`/scans/${scan.id}`}
                        className="flex items-center gap-4 px-4 py-3 hover:bg-bg-card-2 transition-colors"
                    >
                        <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium text-text-1 truncate font-mono">
                                {(scan.repo_url ?? '').replace('https://github.com/', '') || scan.id.slice(0, 8)}
                            </p>
                            <p className="text-[10px] text-text-3">{scan.branch} · {relativeTime(scan.created_at)}</p>
                        </div>
                        <StatusBadge status={scan.status} />
                        {scan.status === 'completed' && scan.summary?.debt_score !== undefined && (
                            <DebtScoreRing score={scan.summary.debt_score} size={32} strokeWidth={3} showLabel={false} animated={false} />
                        )}
                    </Link>
                ))}
            </div>
        </div>
    );
}

/* ── Dashboard Page ──────────────────────────────────────────────────── */

export default function DashboardPage() {
    const user = useAuthStore((s) => s.user);

    // Fetch user's org to establish Dashboard WS connection
    const { data: orgs } = useQuery({
        queryKey: ['organizations'],
        queryFn: () => request<any>('/api/v1/organizations')
    });
    const orgId = orgs?.organizations?.[0]?.id;
    useDashboardWS(orgId);

    const { data, isLoading } = useScans({ limit: 10 });
    const scans = data?.scans ?? [];
    const latestCompleted = scans.find((s) => s.status === 'completed') ?? null;
    const summary = latestCompleted?.summary;

    return (
        <motion.div {...pageVariants} className="space-y-6 max-w-[1400px]">
            {/* Row 1: Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-lg font-semibold text-text-1">
                        Welcome back{user?.name ? `, ${user.name}` : ''}
                    </h1>
                    <p className="text-xs text-text-2">Your codebase health at a glance</p>
                </div>
                <Link
                    href="/scans/new"
                    className="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors"
                >
                    <Plus className="w-4 h-4" />
                    Run New Scan
                </Link>
            </div>

            {/* Row 2: Metric Cards */}
            {isLoading ? (
                <div className="grid grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
            ) : (
                <div className="grid grid-cols-4 gap-4">
                    <MetricCard
                        label="Debt Score"
                        value={summary?.debt_score ?? 0}
                        icon={Activity}
                        subtitle={summary?.grade ? `Grade ${summary.grade}` : 'No scans yet'}
                        color="text-brand"
                    />
                    <MetricCard
                        label="Issues Detected"
                        value={summary?.total_issues ?? 0}
                        icon={AlertTriangle}
                        subtitle="From latest scan"
                        color="text-accent-amber"
                    />
                    <MetricCard
                        label="Critical Issues"
                        value={summary?.critical ?? 0}
                        icon={Shield}
                        subtitle="Needs attention"
                        color="text-sev-critical"
                    />
                    <MetricCard
                        label="AI Fixes"
                        value={summary?.fixes_proposed ?? 0}
                        icon={Wrench}
                        subtitle="Ready to apply"
                        color="text-accent-cyan"
                    />
                </div>
            )}

            {/* Row 3: Pipeline */}
            <ScanPipelineViz latestScan={latestCompleted} />

            {/* Row 4: Three columns */}
            <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                    {isLoading ? <SkeletonTable /> : <RecentScansTable scans={scans} />}
                </div>
                <div className="space-y-4">
                    <DebtHeatmap hotspots={latestCompleted?.hotspots ?? []} />
                    <AIInsightsPanel scan={latestCompleted} />
                </div>
            </div>
        </motion.div>
    );
}
