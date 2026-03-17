'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Calendar, Zap, AlertTriangle, ArrowRight, ShieldAlert, CheckCircle2 } from 'lucide-react';
import type { RankedIssue, EffortLevel } from '@/types/api';
import { SeverityBadge } from '../ui/SeverityBadge';
import { cn } from '@/lib/utils/cn';

interface SprintBucket {
    id: 1 | 2 | 3;
    title: string;
    description: string;
    issues: RankedIssue[];
    totalScore: number;
    effortBreakdown: Record<EffortLevel, number>;
}

const EFFORT_COLORS: Record<EffortLevel, string> = {
    MINUTES: 'text-brand',
    HOURS: 'text-sev-high',
    DAYS: 'text-sev-critical',
};

export function SprintPlannerView({ issues }: { issues: RankedIssue[] }) {
    const buckets = useMemo(() => {
        const b: Record<1 | 2 | 3, SprintBucket> = {
            1: { id: 1, title: 'Sprint 1: Immediate Impact', description: 'Quick wins and critical security fixes.', issues: [], totalScore: 0, effortBreakdown: { MINUTES: 0, HOURS: 0, DAYS: 0 } },
            2: { id: 2, title: 'Sprint 2: Core Refactoring', description: 'Medium effort structural improvements.', issues: [], totalScore: 0, effortBreakdown: { MINUTES: 0, HOURS: 0, DAYS: 0 } },
            3: { id: 3, title: 'Sprint 3: Deep Clean', description: 'Heavy rewrites and low-priority tasks.', issues: [], totalScore: 0, effortBreakdown: { MINUTES: 0, HOURS: 0, DAYS: 0 } },
        };

        for (const issue of issues) {
            const bucket = b[issue.recommended_sprint as 1 | 2 | 3];
            if (!bucket) continue;
            bucket.issues.push(issue);
            bucket.totalScore += issue.score;
            bucket.effortBreakdown[issue.effort_to_fix] = (bucket.effortBreakdown[issue.effort_to_fix] || 0) + 1;
        }

        // Sort issues within buckets by score
        for (const k of [1, 2, 3] as const) {
            b[k].issues.sort((a, b) => b.score - a.score);
        }

        return [b[1], b[2], b[3]];
    }, [issues]);

    return (
        <div className="flex-1 overflow-auto bg-bg-app p-6">
            <div className="max-w-7xl mx-auto space-y-6">
                <div>
                    <h2 className="text-xl font-semibold text-text-1 flex items-center gap-2">
                        <Calendar className="w-5 h-5 text-brand" /> AI Sprint Planner
                    </h2>
                    <p className="text-sm text-text-3 mt-1">
                        Technical debt grouped automatically by severity, effort, and dependency loops.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {buckets.map((bucket, i) => (
                        <motion.div
                            key={bucket.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="flex flex-col h-[calc(100vh-14rem)] bg-bg-card border border-border rounded-xl overflow-hidden shadow-sm"
                        >
                            <div className="p-4 border-b border-border bg-bg-elevated">
                                <h3 className="text-sm font-semibold text-text-1 mb-1">{bucket.title}</h3>
                                <p className="text-[11px] text-text-3 mb-4">{bucket.description}</p>

                                <div className="flex items-center justify-between text-xs">
                                    <span className="font-medium text-text-2">{bucket.issues.length} issues</span>
                                    <div className="flex items-center gap-3">
                                        <span className="flex items-center gap-1 text-text-3" title="Minutes">
                                            <span className="w-2 h-2 rounded-full bg-brand"></span> {bucket.effortBreakdown.MINUTES}
                                        </span>
                                        <span className="flex items-center gap-1 text-text-3" title="Hours">
                                            <span className="w-2 h-2 rounded-full bg-sev-high"></span> {bucket.effortBreakdown.HOURS}
                                        </span>
                                        <span className="flex items-center gap-1 text-text-3" title="Days">
                                            <span className="w-2 h-2 rounded-full bg-sev-critical"></span> {bucket.effortBreakdown.DAYS}
                                        </span>
                                    </div>
                                </div>
                                <div className="mt-4 flex items-center gap-2">
                                    <div className="h-1.5 flex-1 bg-border rounded-full overflow-hidden flex">
                                        <div className="h-full bg-sev-critical" style={{ width: `${(bucket.totalScore / (buckets[0].totalScore + buckets[1].totalScore + buckets[2].totalScore || 1)) * 100}%` }} />
                                    </div>
                                    <span className="text-[10px] font-mono font-medium text-text-2">{bucket.totalScore} pts</span>
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
                                {bucket.issues.map((issue) => (
                                    <div key={issue.id} className="p-3 rounded-lg bg-bg-card-2 border border-border group hover:border-brand/40 transition-colors">
                                        <div className="flex items-start justify-between mb-2">
                                            <SeverityBadge severity={issue.severity} />
                                            <span className={cn("text-[10px] font-bold tracking-wider", EFFORT_COLORS[issue.effort_to_fix])}>
                                                {issue.effort_to_fix}
                                            </span>
                                        </div>
                                        <p className="text-xs font-medium text-text-1 line-clamp-2 leading-relaxed">
                                            {issue.title}
                                        </p>
                                        <p className="text-[10px] font-mono text-text-code mt-2 truncate">
                                            {issue.location.file_path}
                                        </p>
                                        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border/50">
                                            <span className="text-[10px] font-medium text-text-3">Score: {issue.score}</span>
                                            {issue.quick_win && <span className="flex items-center gap-1 text-[10px] text-brand font-medium"><Zap className="w-3 h-3" /> Quick Win</span>}
                                            {issue.blocks_other_work && <span className="flex items-center gap-1 text-[10px] text-sev-high font-medium"><AlertTriangle className="w-3 h-3" /> Blocker</span>}
                                        </div>
                                    </div>
                                ))}
                                {bucket.issues.length === 0 && (
                                    <div className="text-center py-8 text-xs text-text-3">
                                        No items planned for this sprint.
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    );
}
