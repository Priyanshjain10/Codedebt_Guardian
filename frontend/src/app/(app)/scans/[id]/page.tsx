'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { FileText, AlertTriangle, Wrench, Bot, BarChart3, Clock, GitBranch, Download } from 'lucide-react';
import { useScan } from '@/lib/hooks/useScans';
import { DebtScoreRing } from '@/components/ui/DebtScoreRing';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { SeverityBadge } from '@/components/ui/SeverityBadge';
import { SkeletonCard } from '@/components/ui/SkeletonCard';
import { getScanReportUrl } from '@/lib/api/scans';
import { formatDuration, relativeTime } from '@/lib/utils/formatters';
import { cn } from '@/lib/utils/cn';

const TABS = [
    { id: 'overview', label: 'Overview' },
    { id: 'issues', label: 'Issues' },
    { id: 'fixes', label: 'Fixes' },
    { id: 'autopilot', label: 'Autopilot' },
    { id: 'report', label: 'Report' },
] as const;

export default function ScanOverviewPage() {
    const params = useParams();
    const scanId = params.id as string;
    const { data: scan, isLoading } = useScan(scanId);

    if (isLoading) {
        return (
            <div className="grid grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
        );
    }

    if (!scan) return <div className="text-text-3 text-sm">Scan not found</div>;

    const summary = scan.summary;
    const issueCount = summary?.total_issues ?? scan.ranked_issues?.length ?? 0;
    const fixCount = summary?.fixes_proposed ?? scan.fix_proposals?.length ?? 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6 max-w-[1200px]"
        >
            {/* Sub-nav tabs */}
            <div className="flex items-center gap-1 border-b border-border pb-px">
                {TABS.map((tab) => {
                    const isActive = tab.id === 'overview';
                    const count = tab.id === 'issues' ? issueCount : tab.id === 'fixes' ? fixCount : null;
                    return (
                        <Link
                            key={tab.id}
                            href={tab.id === 'overview' ? `/scans/${scanId}` : `/scans/${scanId}/${tab.id}`}
                            className={cn(
                                'px-3 py-2 text-xs font-medium transition-colors border-b-2 -mb-px',
                                isActive
                                    ? 'text-brand border-brand'
                                    : 'text-text-3 border-transparent hover:text-text-2',
                            )}
                        >
                            {tab.label}
                            {count !== null && (
                                <span className="ml-1.5 text-[10px] px-1 py-0.5 rounded bg-bg-card-2 text-text-3">
                                    {count}
                                </span>
                            )}
                        </Link>
                    );
                })}
            </div>

            {/* Hero: Score + Status */}
            <div className="flex items-start gap-8">
                <DebtScoreRing
                    score={summary?.debt_score ?? 0}
                    grade={summary?.grade}
                    size={120}
                    animated
                    showLabel
                />
                <div className="flex-1 space-y-3">
                    <div className="flex items-center gap-3">
                        <StatusBadge status={scan.status} />
                        <span className="text-xs text-text-3">{relativeTime(scan.created_at)}</span>
                    </div>
                    <p className="text-sm font-mono text-text-code">
                        {scan.repo_url?.replace('https://github.com/', '')}
                    </p>
                    <div className="flex items-center gap-4 text-xs text-text-2">
                        <span className="flex items-center gap-1">
                            <GitBranch className="w-3 h-3" /> {scan.branch}
                        </span>
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" /> {formatDuration(scan.duration_seconds)}
                        </span>
                    </div>
                </div>
                {scan.status === 'completed' && (
                    <a
                        href={getScanReportUrl(scanId, 'pdf')}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 h-8 px-3 rounded-lg border border-border text-xs text-text-2 hover:text-text-1 hover:border-border-strong transition-colors"
                    >
                        <Download className="w-3.5 h-3.5" />
                        Download Report
                    </a>
                )}
            </div>

            {/* Summary grid */}
            {summary && (
                <div className="grid grid-cols-4 gap-4">
                    <div className="bg-bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-text-3 mb-1">Critical</div>
                        <div className="text-xl font-bold font-mono text-sev-critical">{summary.critical ?? 0}</div>
                    </div>
                    <div className="bg-bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-text-3 mb-1">High</div>
                        <div className="text-xl font-bold font-mono text-sev-high">{summary.high ?? 0}</div>
                    </div>
                    <div className="bg-bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-text-3 mb-1">Medium</div>
                        <div className="text-xl font-bold font-mono text-sev-medium">{summary.medium ?? 0}</div>
                    </div>
                    <div className="bg-bg-card border border-border rounded-xl p-4">
                        <div className="text-xs text-text-3 mb-1">Low</div>
                        <div className="text-xl font-bold font-mono text-sev-low">{summary.low ?? 0}</div>
                    </div>
                </div>
            )}

            {/* TDR */}
            {scan.tdr && (
                <div className="bg-bg-card border border-border rounded-xl p-5">
                    <h3 className="text-xs font-semibold text-text-2 mb-3">Technical Debt Ratio (TDR)</h3>
                    <div className="flex items-center gap-8">
                        <div>
                            <span className="text-2xl font-bold font-mono text-brand">
                                {(scan.tdr.ratio * 100).toFixed(1)}%
                            </span>
                            <span className="ml-2 text-xs text-text-3">({scan.tdr.rating})</span>
                        </div>
                        <div className="text-xs text-text-2">
                            <span className="text-text-3">Debt: </span>
                            {Math.round(scan.tdr.total_debt_minutes)} min
                            <span className="mx-2 text-text-3"> / </span>
                            <span className="text-text-3">Total: </span>
                            {Math.round(scan.tdr.total_work_minutes)} min
                        </div>
                    </div>
                </div>
            )}
        </motion.div>
    );
}
