'use client';

import { useState, useMemo, useCallback } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef } from 'react';
import { motion } from 'framer-motion';
import { Search, Filter, ExternalLink, ChevronRight } from 'lucide-react';
import { useScan } from '@/lib/hooks/useScans';
import { SeverityBadge } from '@/components/ui/SeverityBadge';
import { SkeletonTable } from '@/components/ui/SkeletonCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { AIExplanationBox } from '@/components/issues/AIExplanationBox';
import { SprintPlannerView } from '@/components/issues/SprintPlannerView';
import { cn } from '@/lib/utils/cn';
import { useFilterStore } from '@/store/filterStore';
import type { RankedIssue, FixProposal, DebtSeverity, DebtCategory } from '@/types/api';

const SEVERITY_ORDER: Record<DebtSeverity, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export default function IssueExplorerPage() {
    const params = useParams();
    const searchParams = useSearchParams();
    const scanId = params.id as string;
    const { data: scan, isLoading } = useScan(scanId);

    const [viewMode, setViewMode] = useState<'explorer' | 'sprint'>('explorer');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const listRef = useRef<HTMLDivElement>(null);

    const {
        severity: severityFilter,
        setSeverity,
        searchQuery,
        setSearchQuery,
        showQuickWins,
        setShowQuickWins,
        sortBy,
        setSortBy,
    } = useFilterStore();

    // Apply URL params as initial filters
    const categoryParam = searchParams.get('category') as DebtCategory | null;
    const quickWinParam = searchParams.get('quick_win');

    const allIssues: RankedIssue[] = scan?.ranked_issues ?? [];
    const allFixes: FixProposal[] = scan?.fix_proposals ?? [];

    // Filter and sort issues
    const filteredIssues = useMemo(() => {
        let result = [...allIssues];

        // Severity filter
        if (severityFilter.length > 0) {
            result = result.filter((i) => severityFilter.includes(i.severity));
        }

        // Category from URL param
        if (categoryParam) {
            result = result.filter((i) => i.category === categoryParam);
        }

        // Quick wins
        if (showQuickWins || quickWinParam === 'true') {
            result = result.filter((i) => i.quick_win);
        }

        // Search
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            result = result.filter(
                (i) =>
                    i.title.toLowerCase().includes(q) ||
                    i.location.file_path.toLowerCase().includes(q) ||
                    i.description.toLowerCase().includes(q),
            );
        }

        // Sort
        switch (sortBy) {
            case 'score':
                result.sort((a, b) => b.score - a.score);
                break;
            case 'severity':
                result.sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
                break;
            case 'file':
                result.sort((a, b) => a.location.file_path.localeCompare(b.location.file_path));
                break;
            case 'effort':
                result.sort((a, b) => {
                    const order = { MINUTES: 0, HOURS: 1, DAYS: 2 };
                    return order[a.effort_to_fix] - order[b.effort_to_fix];
                });
                break;
        }

        return result;
    }, [allIssues, severityFilter, categoryParam, showQuickWins, quickWinParam, searchQuery, sortBy]);

    const selectedIssue = filteredIssues[selectedIndex] ?? null;
    const matchingFix = selectedIssue
        ? allFixes.find((f) => f.issue_type === selectedIssue.type) ?? null
        : null;

    // Virtualized list
    const virtualizer = useVirtualizer({
        count: filteredIssues.length,
        getScrollElement: () => listRef.current,
        estimateSize: () => 72,
        overscan: 10,
    });

    // Keyboard navigation
    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setSelectedIndex((p) => Math.min(p + 1, filteredIssues.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setSelectedIndex((p) => Math.max(p - 1, 0));
            }
        },
        [filteredIssues.length],
    );

    if (isLoading) return <SkeletonTable rows={10} />;

    return (
        <div className="flex flex-col h-[calc(100vh-7rem)] -m-6">
            <div className="h-12 border-b border-border bg-bg-card flex items-center px-6 shrink-0 gap-6">
                <button
                    onClick={() => setViewMode('explorer')}
                    className={cn(
                        "text-sm font-medium transition-colors h-full border-b-2",
                        viewMode === 'explorer' ? "text-brand border-brand" : "text-text-3 border-transparent hover:text-text-2"
                    )}
                >
                    Issue Explorer
                </button>
                <button
                    onClick={() => setViewMode('sprint')}
                    className={cn(
                        "text-sm font-medium transition-colors h-full border-b-2 flex items-center gap-2",
                        viewMode === 'sprint' ? "text-brand border-brand" : "text-text-3 border-transparent hover:text-text-2"
                    )}
                >
                    Sprint Planner
                </button>
            </div>

            {viewMode === 'explorer' ? (
                <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.18 }}
                    className="flex flex-1 gap-0 min-h-0"
                    onKeyDown={handleKeyDown}
                    tabIndex={0}
                >
                    {/* ── Left Panel: Issue List ──────────────────────────────── */}
                    <div className="w-[300px] shrink-0 border-r border-border flex flex-col bg-bg-elevated">
                        {/* Filter bar */}
                        <div className="p-3 border-b border-border space-y-2">
                            <div className="relative">
                                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-3" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Search issues..."
                                    className="w-full h-8 pl-8 pr-3 rounded-lg bg-bg-input border border-border text-xs text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-1 focus:ring-brand/30"
                                />
                            </div>
                            <div className="flex items-center gap-1 flex-wrap">
                                {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as DebtSeverity[]).map((sev) => (
                                    <button
                                        key={sev}
                                        onClick={() => {
                                            if (severityFilter.includes(sev)) {
                                                setSeverity(severityFilter.filter((s) => s !== sev));
                                            } else {
                                                setSeverity([...severityFilter, sev]);
                                            }
                                        }}
                                        className={cn(
                                            'text-[10px] px-1.5 py-0.5 rounded font-medium transition-colors',
                                            severityFilter.includes(sev)
                                                ? 'bg-brand-dim text-brand'
                                                : 'bg-bg-card text-text-3 hover:text-text-2',
                                        )}
                                    >
                                        {sev}
                                    </button>
                                ))}
                                <button
                                    onClick={() => setShowQuickWins(!showQuickWins)}
                                    className={cn(
                                        'text-[10px] px-1.5 py-0.5 rounded font-medium transition-colors',
                                        showQuickWins
                                            ? 'bg-brand-dim text-brand'
                                            : 'bg-bg-card text-text-3 hover:text-text-2',
                                    )}
                                >
                                    ⚡ Quick
                                </button>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-[10px] text-text-3">{filteredIssues.length} issues</span>
                                <select
                                    value={sortBy}
                                    onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
                                    className="text-[10px] bg-bg-input border border-border rounded px-1.5 py-0.5 text-text-2 focus:outline-none"
                                >
                                    <option value="score">Score</option>
                                    <option value="severity">Severity</option>
                                    <option value="file">File</option>
                                    <option value="effort">Effort</option>
                                </select>
                            </div>
                        </div>

                        {/* Virtualized issue list */}
                        <div ref={listRef} className="flex-1 overflow-y-auto scrollbar-thin">
                            {filteredIssues.length === 0 ? (
                                <div className="p-4 text-center text-xs text-text-3">No issues match filters</div>
                            ) : (
                                <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
                                    {virtualizer.getVirtualItems().map((vItem) => {
                                        const issue = filteredIssues[vItem.index];
                                        const isSelected = vItem.index === selectedIndex;
                                        return (
                                            <div
                                                key={issue.id}
                                                data-index={vItem.index}
                                                ref={virtualizer.measureElement}
                                                onClick={() => setSelectedIndex(vItem.index)}
                                                className={cn(
                                                    'absolute top-0 left-0 w-full px-3 py-2.5 cursor-pointer border-l-2 transition-colors',
                                                    isSelected
                                                        ? 'bg-brand-dim border-l-brand'
                                                        : 'border-l-transparent hover:bg-bg-card-2',
                                                )}
                                                style={{ transform: `translateY(${vItem.start}px)` }}
                                            >
                                                <div className="flex items-start gap-2">
                                                    <SeverityBadge severity={issue.severity} />
                                                    <div className="min-w-0 flex-1">
                                                        <p className="text-xs font-medium text-text-1 truncate">{issue.title}</p>
                                                        <p className="text-[10px] text-text-code font-mono truncate mt-0.5">
                                                            {issue.location.file_path}
                                                            {issue.location.line_start ? `:${issue.location.line_start}` : ''}
                                                        </p>
                                                        <div className="flex items-center gap-2 mt-1">
                                                            <span className="text-[10px] text-text-3 font-mono">Score: {issue.score}</span>
                                                            {issue.quick_win && <span className="text-[10px] text-brand">⚡</span>}
                                                            {issue.blocks_other_work && <span className="text-[10px] text-sev-high">🔗</span>}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* ── Center Panel: Issue Detail ─────────────────────────── */}
                    <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
                        {selectedIssue ? (
                            <AIExplanationBox issue={selectedIssue} fix={matchingFix ?? undefined} />
                        ) : (
                            <EmptyState
                                icon={Filter}
                                title="Select an issue"
                                description="Click on an issue from the list to view its AI analysis"
                            />
                        )}
                    </div>

                    {/* ── Right Panel: Code Context ──────────────────────────── */}
                    <div className="w-[380px] shrink-0 border-l border-border bg-bg-elevated overflow-y-auto scrollbar-thin p-4">
                        {selectedIssue ? (
                            <div className="space-y-4">
                                {/* File header */}
                                <div className="flex items-center justify-between">
                                    <p className="text-xs font-mono text-text-code truncate flex-1">{selectedIssue.location.file_path}</p>
                                    {selectedIssue.location.line_start && (
                                        <span className="text-[10px] text-text-3 shrink-0 ml-2">
                                            L{selectedIssue.location.line_start}
                                            {selectedIssue.location.line_end ? `–${selectedIssue.location.line_end}` : ''}
                                        </span>
                                    )}
                                </div>

                                {/* Code snippet */}
                                {selectedIssue.code_snippet ? (
                                    <div className="bg-bg-code border border-border rounded-lg overflow-hidden">
                                        <div className="px-3 py-2 border-b border-border flex items-center justify-between">
                                            <span className="text-[10px] text-text-3 font-mono">
                                                {selectedIssue.location.function_name ?? selectedIssue.location.class_name ?? 'Code'}
                                            </span>
                                        </div>
                                        <pre className="p-3 text-xs font-mono text-text-1 overflow-x-auto scrollbar-thin whitespace-pre leading-relaxed">
                                            {selectedIssue.code_snippet}
                                        </pre>
                                    </div>
                                ) : (
                                    <div className="bg-bg-code border border-border rounded-lg p-6 text-center">
                                        <p className="text-xs text-text-3">No code snippet available</p>
                                    </div>
                                )}

                                {/* External link */}
                                {scan?.repo_url && (
                                    <a
                                        href={`${scan.repo_url}/blob/${scan.branch}/${selectedIssue.location.file_path}${selectedIssue.location.line_start ? `#L${selectedIssue.location.line_start}` : ''}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex items-center gap-1.5 text-xs text-brand hover:text-brand-light transition-colors"
                                    >
                                        <ExternalLink className="w-3 h-3" />
                                        View on GitHub
                                    </a>
                                )}

                                {/* Context info */}
                                {selectedIssue.location.function_name && (
                                    <div className="text-xs">
                                        <span className="text-text-3">Function: </span>
                                        <span className="text-text-code font-mono">{selectedIssue.location.function_name}</span>
                                    </div>
                                )}
                                {selectedIssue.location.class_name && (
                                    <div className="text-xs">
                                        <span className="text-text-3">Class: </span>
                                        <span className="text-text-code font-mono">{selectedIssue.location.class_name}</span>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-center py-12">
                                <p className="text-xs text-text-3">Select an issue to view code context</p>
                            </div>
                        )}
                    </div>
                </motion.div>
            ) : (
                <SprintPlannerView issues={allIssues} />
            )}
        </div>
    );
}
