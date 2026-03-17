'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ScanSearch, Plus } from 'lucide-react';
import { useScans } from '@/lib/hooks/useScans';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { DebtScoreRing } from '@/components/ui/DebtScoreRing';
import { SkeletonTable } from '@/components/ui/SkeletonCard';
import { EmptyState } from '@/components/ui/EmptyState';
import { relativeTime, formatDuration } from '@/lib/utils/formatters';

export default function ScansListPage() {
    const router = useRouter();
    const { data, isLoading } = useScans({ limit: 50 });
    const scans = data?.scans ?? [];

    if (isLoading) return <SkeletonTable rows={8} />;

    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 max-w-[1200px]">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-text-1">Scans</h1>
                <Link
                    href="/scans/new"
                    className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors"
                >
                    <Plus className="w-3.5 h-3.5" /> New Scan
                </Link>
            </div>

            {scans.length === 0 ? (
                <EmptyState
                    icon={ScanSearch}
                    title="No scans yet"
                    description="Run your first scan to start analyzing technical debt"
                    action={{ label: 'Run Scan', onClick: () => router.push('/scans/new') }}
                />
            ) : (
                <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-border text-[10px] text-text-3 uppercase tracking-wider">
                                <th className="text-left px-4 py-2.5 font-medium">Repository</th>
                                <th className="text-left px-4 py-2.5 font-medium">Branch</th>
                                <th className="text-left px-4 py-2.5 font-medium">Status</th>
                                <th className="text-center px-4 py-2.5 font-medium">Score</th>
                                <th className="text-right px-4 py-2.5 font-medium">Duration</th>
                                <th className="text-right px-4 py-2.5 font-medium">Created</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                            {scans.map((scan) => (
                                <tr
                                    key={scan.id}
                                    onClick={() => router.push(`/scans/${scan.id}`)}
                                    className="hover:bg-bg-card-2 cursor-pointer transition-colors"
                                >
                                    <td className="px-4 py-3">
                                        <span className="text-xs font-mono text-text-code">
                                            {scan.repo_url?.replace('https://github.com/', '') ?? scan.id.slice(0, 8)}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-xs text-text-2">{scan.branch}</td>
                                    <td className="px-4 py-3">
                                        <StatusBadge status={scan.status} />
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        {scan.status === 'completed' && scan.summary?.debt_score !== undefined ? (
                                            <DebtScoreRing score={scan.summary.debt_score} size={28} strokeWidth={2.5} showLabel={false} animated={false} />
                                        ) : (
                                            <span className="text-text-3 text-xs">—</span>
                                        )}
                                    </td>
                                    <td className="px-4 py-3 text-right text-xs text-text-2 font-mono">
                                        {formatDuration(scan.duration_seconds)}
                                    </td>
                                    <td className="px-4 py-3 text-right text-xs text-text-3">
                                        {relativeTime(scan.created_at)}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </motion.div>
    );
}
