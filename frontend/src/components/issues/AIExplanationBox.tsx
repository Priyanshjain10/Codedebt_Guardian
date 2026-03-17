'use client';

import { cn } from '@/lib/utils/cn';
import { SeverityBadge } from '@/components/ui/SeverityBadge';
import { getSourceLabel, getEffortLabel } from '@/lib/utils/severity';
import type { RankedIssue, FixProposal } from '@/types/api';

interface AIExplanationBoxProps {
    issue: RankedIssue;
    fix?: FixProposal;
}

/**
 * Core value display of the product — three distinct sections:
 * 1. AI Analysis — issue.description
 * 2. Business Impact — issue.impact + business_justification (amber callout)
 * 3. Fix Summary — from matching FixProposal (green callout)
 */
export function AIExplanationBox({ issue, fix }: AIExplanationBoxProps) {
    return (
        <div className="space-y-4">
            {/* Header with metadata */}
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                    <h2 className="text-sm font-semibold text-text-1 mb-1">{issue.title}</h2>
                    <div className="flex items-center flex-wrap gap-2">
                        <SeverityBadge severity={issue.severity} pulse={issue.severity === 'CRITICAL'} />
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-card-2 text-text-2 font-mono">
                            {getSourceLabel(issue.source)}
                        </span>
                        {issue.quick_win && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-dim text-brand font-medium flex items-center gap-1">
                                ⚡ Quick Win
                            </span>
                        )}
                        {issue.blocks_other_work && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-sev-high-bg text-sev-high font-medium flex items-center gap-1">
                                🔗 Blocks Work
                            </span>
                        )}
                    </div>
                </div>
                <div className="text-right shrink-0">
                    <div className="text-lg font-bold font-mono text-text-1">{issue.score}</div>
                    <div className="text-[10px] text-text-3">Score</div>
                </div>
            </div>

            {/* Metadata row */}
            <div className="grid grid-cols-4 gap-3 text-xs">
                <div>
                    <span className="text-text-3 block mb-0.5">Category</span>
                    <span className="text-text-1 capitalize">{issue.category}</span>
                </div>
                <div>
                    <span className="text-text-3 block mb-0.5">Effort</span>
                    <span className="text-text-1">{getEffortLabel(issue.effort_to_fix)}</span>
                </div>
                <div>
                    <span className="text-text-3 block mb-0.5">Sprint</span>
                    <span className="text-text-1">Sprint {issue.recommended_sprint}</span>
                </div>
                <div>
                    <span className="text-text-3 block mb-0.5">Confidence</span>
                    <div className="flex items-center gap-1.5">
                        <div className="flex-1 h-1 rounded-full bg-bg-card-2 overflow-hidden">
                            <div
                                className="h-full rounded-full bg-brand"
                                style={{ width: `${Math.round(issue.confidence * 100)}%` }}
                            />
                        </div>
                        <span className="text-text-1 font-mono text-[10px]">{Math.round(issue.confidence * 100)}%</span>
                    </div>
                </div>
            </div>

            {/* Section 1: AI Analysis */}
            <div className="bg-bg-card-2 border border-border rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">✦</span>
                    <h3 className="text-xs font-semibold text-text-1">AI Analysis</h3>
                </div>
                <p className="text-xs text-text-2 leading-relaxed">{issue.description}</p>
            </div>

            {/* Section 2: Business Impact — amber callout */}
            <div className="bg-accent-amber/5 border border-accent-amber/20 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">⚠</span>
                    <h3 className="text-xs font-semibold text-accent-amber">Business Impact</h3>
                </div>
                <p className="text-xs text-text-2 leading-relaxed mb-2">{issue.impact}</p>
                {issue.business_justification && (
                    <p className="text-xs text-text-2 leading-relaxed italic border-t border-accent-amber/10 pt-2 mt-2">
                        {issue.business_justification}
                    </p>
                )}
            </div>

            {/* Section 3: Fix Summary — green callout */}
            {fix ? (
                <div className="bg-brand/5 border border-brand/20 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm">💡</span>
                        <h3 className="text-xs font-semibold text-brand">Fix Summary</h3>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-dim text-brand font-mono ml-auto">
                            {fix.source}
                        </span>
                    </div>
                    <p className="text-xs text-text-2 leading-relaxed mb-3">{fix.fix_summary}</p>
                    {fix.steps.length > 0 && (
                        <ol className="space-y-1">
                            {fix.steps.map((step, i) => (
                                <li key={i} className="flex gap-2 text-xs text-text-2">
                                    <span className="text-brand font-mono shrink-0">{i + 1}.</span>
                                    <span>{step}</span>
                                </li>
                            ))}
                        </ol>
                    )}
                </div>
            ) : (
                <div className="bg-bg-card-2 border border-border rounded-lg p-4 text-center">
                    <p className="text-xs text-text-3">No AI fix proposal available for this issue</p>
                </div>
            )}
        </div>
    );
}
