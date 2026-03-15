'use client';

import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { CheckCircle2, Clock, ExternalLink, GitPullRequest } from 'lucide-react';
import { useScan } from '@/lib/hooks/useScans';
import { SkeletonCard } from '@/components/ui/SkeletonCard';
import { formatDuration, relativeTime } from '@/lib/utils/formatters';

const AGENT_STAGES = [
    { key: 'detection', icon: '🔍', label: 'Debt Detection' },
    { key: 'ranking', icon: '📊', label: 'Priority Ranking' },
    { key: 'fixing', icon: '🔧', label: 'Fix Generation' },
    { key: 'autopilot', icon: '🔀', label: 'PR Creation' },
] as const;

export default function AutopilotPage() {
    const params = useParams();
    const scanId = params.id as string;
    const { data: scan, isLoading } = useScan(scanId);

    if (isLoading) {
        return (
            <div className="grid grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
        );
    }

    if (!scan) return <div className="text-text-3 text-sm">Scan not found</div>;

    const summary = scan.summary;

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-2 gap-6 max-w-[1200px]"
        >
            {/* Left: Agent timeline */}
            <div className="space-y-4">
                <h2 className="text-sm font-semibold text-text-1">Agent Timeline</h2>

                <div className="space-y-0">
                    {AGENT_STAGES.map((stage, i) => (
                        <div key={stage.key} className="flex gap-3">
                            {/* Timeline connector */}
                            <div className="flex flex-col items-center">
                                <div className="w-8 h-8 rounded-full bg-brand/10 flex items-center justify-center shrink-0">
                                    <span className="text-sm">{stage.icon}</span>
                                </div>
                                {i < AGENT_STAGES.length - 1 && (
                                    <div className="w-px h-full bg-border min-h-[40px]" />
                                )}
                            </div>

                            {/* Content */}
                            <div className="pb-4">
                                <div className="flex items-center gap-2 mb-1">
                                    <span className="text-xs font-medium text-text-1">{stage.label}</span>
                                    {scan.status === 'completed' && (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-brand" />
                                    )}
                                </div>
                                <p className="text-[10px] text-text-3">
                                    {stage.key === 'detection' && `${summary?.total_issues ?? 0} issues found`}
                                    {stage.key === 'ranking' && `${summary?.critical ?? 0} critical, ${summary?.high ?? 0} high, ${summary?.medium ?? 0} medium, ${summary?.low ?? 0} low`}
                                    {stage.key === 'fixing' && `${summary?.fixes_proposed ?? 0} fix proposals generated`}
                                    {stage.key === 'autopilot' && 'Agent pipeline complete'}
                                </p>
                                {stage.key === 'detection' && scan.duration_seconds && (
                                    <p className="text-[10px] text-text-3 flex items-center gap-1 mt-0.5">
                                        <Clock className="w-3 h-3" /> {formatDuration(scan.duration_seconds)}
                                    </p>
                                )}
                                {summary?.tokens_input !== undefined && stage.key === 'detection' && (
                                    <p className="text-[10px] text-text-3 mt-0.5">
                                        Tokens: {(summary.tokens_input ?? 0).toLocaleString()} in / {(summary.tokens_output ?? 0).toLocaleString()} out
                                    </p>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Right: PR Status Cards */}
            <div className="space-y-4">
                <h2 className="text-sm font-semibold text-text-1">Pull Requests</h2>

                {(scan.fix_proposals ?? []).length === 0 ? (
                    <div className="bg-bg-card border border-border rounded-xl p-6 text-center">
                        <GitPullRequest className="w-8 h-8 text-text-3 mx-auto mb-2" />
                        <p className="text-xs text-text-3">No PRs created for this scan</p>
                        <p className="text-[10px] text-text-3 mt-1">Apply fixes from the Fixes tab to create PRs</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {(scan.fix_proposals ?? []).slice(0, 5).map((fix, i) => (
                            <div key={i} className="bg-bg-card border border-border rounded-xl p-4">
                                <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                        <p className="text-xs font-medium text-text-1 truncate">{fix.problem_summary}</p>
                                        <p className="text-[10px] text-text-3 mt-0.5">
                                            {fix.source === 'ai' ? '✦ AI Generated' : fix.source}
                                        </p>
                                    </div>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-dim text-brand font-medium">
                                        Fix Available
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </motion.div>
    );
}
