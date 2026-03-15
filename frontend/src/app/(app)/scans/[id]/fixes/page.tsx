'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2, ExternalLink, GitPullRequest, Lock } from 'lucide-react';
import { toast } from 'sonner';
import { useScan } from '@/lib/hooks/useScans';
import * as scansApi from '@/lib/api/scans';
import { SeverityBadge } from '@/components/ui/SeverityBadge';
import { SkeletonCard } from '@/components/ui/SkeletonCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { cn } from '@/lib/utils/cn';
import ReactDiffViewer from 'react-diff-viewer-continued';
import type { FixProposal, RankedIssue } from '@/types/api';

function FixCard({
    fix,
    index,
    issue,
    scanId,
}: {
    fix: FixProposal;
    index: number;
    issue: RankedIssue | undefined;
    scanId: string;
}) {
    const [creating, setCreating] = useState(false);
    const [prUrl, setPrUrl] = useState<string | null>(null);

    const handleCreatePR = async () => {
        setCreating(true);
        try {
            const result = await scansApi.createFixPR(scanId, index);
            setPrUrl(result.pr_url);
            toast.success(`PR #${result.pr_number} created: ${result.title}`);
        } catch (err: unknown) {
            const apiError = err as { status?: number; message?: string };
            if (apiError.status === 402) {
                toast.error('Auto-PR requires Pro plan. Upgrade to create pull requests.');
            } else {
                toast.error(apiError.message || 'Failed to create PR');
            }
        } finally {
            setCreating(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-bg-card border border-border rounded-xl overflow-hidden"
        >
            {/* Header */}
            <div className="px-5 py-4 border-b border-border">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                            {issue && <SeverityBadge severity={issue.severity} />}
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-card-2 text-text-2 font-mono">
                                {fix.source === 'ai' ? '✦ AI Generated' : fix.source === 'template' ? '📋 Template' : '🔄 Fallback'}
                            </span>
                        </div>
                        <h3 className="text-sm font-medium text-text-1">{fix.problem_summary}</h3>
                    </div>
                </div>
            </div>

            {/* Diff viewer */}
            <div className="border-t border-border overflow-hidden">
                <ReactDiffViewer
                    oldValue={fix.before_code}
                    newValue={fix.after_code}
                    splitView={true}
                    useDarkTheme={true}
                    styles={{
                        variables: {
                            dark: {
                                diffViewerBackground: 'var(--bg-code)',
                                addedBackground: 'rgba(16,185,129,0.1)',
                                removedBackground: 'rgba(239,68,68,0.08)',
                            }
                        }
                    }}
                />
            </div>

            {/* Steps */}
            {fix.steps.length > 0 && (
                <div className="px-5 py-3 border-t border-border">
                    <p className="text-[10px] font-semibold text-text-3 uppercase tracking-wider mb-2">Steps</p>
                    <ol className="space-y-1">
                        {fix.steps.map((step, i) => (
                            <li key={i} className="text-xs text-text-2 flex gap-2">
                                <span className="text-brand font-mono shrink-0">{i + 1}.</span>
                                {step}
                            </li>
                        ))}
                    </ol>
                </div>
            )}

            {/* Actions */}
            <div className="px-5 py-3 border-t border-border flex items-center gap-2">
                {prUrl ? (
                    <a
                        href={prUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                        View PR
                    </a>
                ) : (
                    <button
                        onClick={handleCreatePR}
                        disabled={creating}
                        className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors disabled:opacity-50"
                    >
                        {creating ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                            <GitPullRequest className="w-3.5 h-3.5" />
                        )}
                        Create GitHub PR
                    </button>
                )}
            </div>
        </motion.div>
    );
}

export default function FixSuggestionsPage() {
    const params = useParams();
    const scanId = params.id as string;
    const { data: scan, isLoading } = useScan(scanId);

    if (isLoading) {
        return (
            <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} className="h-48" />)}
            </div>
        );
    }

    const fixes = scan?.fix_proposals ?? [];
    const issues = scan?.ranked_issues ?? [];

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4 max-w-[1000px]"
        >
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-text-1">{fixes.length} AI-Generated Fixes</h1>
            </div>

            {fixes.length === 0 ? (
                <EmptyState
                    icon={GitPullRequest}
                    title="No fixes generated"
                    description="This scan did not produce any fix proposals"
                />
            ) : (
                <div className="space-y-4">
                    {fixes.map((fix, i) => (
                        <FixCard
                            key={fix.id || i}
                            fix={fix}
                            index={i}
                            issue={issues.find((iss) => iss.type === fix.issue_type)}
                            scanId={scanId}
                        />
                    ))}
                </div>
            )}
        </motion.div>
    );
}
