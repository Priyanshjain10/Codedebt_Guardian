'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, useMotionValue, useSpring, AnimatePresence } from 'framer-motion';
import {
    Shield, AlertTriangle, Wrench, GitPullRequest,
    TrendingUp, TrendingDown, Activity, Zap, ArrowRight,
    ChevronRight, Clock, Star, Target, Cpu, BarChart2,
    ExternalLink, Play
} from 'lucide-react';
import { useScans, useLatestScan } from '@/lib/hooks/useScans';
import { useAuthStore } from '@/store/authStore';
import { useDashboardWS } from '@/lib/hooks/useDashboardWS';
import { useBilling } from '@/lib/hooks/useBilling';
import { request } from '@/lib/api/client';
import { useQuery } from '@tanstack/react-query';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';
import { cn } from '@/lib/utils/cn';
import Link from 'next/link';
import type { Scan } from '@/types/api';

/* ── Animated Number Counter ─────────────────────────────────────────── */
function Counter({ value, duration = 1200 }: { value: number; duration?: number }) {
    const [display, setDisplay] = useState(0);
    useEffect(() => {
        if (!value) return;
        const start = performance.now();
        const tick = (now: number) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplay(Math.round(eased * value));
            if (progress < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    }, [value, duration]);
    return <>{display.toLocaleString()}</>;
}

/* ── Debt Score Ring ─────────────────────────────────────────────────── */
function DebtRing({ score, maxScore = 10000 }: { score: number; maxScore?: number }) {
    const pct = Math.min(score / maxScore, 1);
    const r = 52;
    const circ = 2 * Math.PI * r;
    const dash = circ * (1 - pct);
    const hue = pct > 0.7 ? '#FF2D55' : pct > 0.4 ? '#FFD60A' : '#00F5A0';

    return (
        <div className="relative w-36 h-36 flex items-center justify-center">
            <svg className="absolute inset-0 rotate-[-90deg]" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
                <circle
                    cx="60" cy="60" r={r} fill="none"
                    stroke={hue}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={circ}
                    strokeDashoffset={dash}
                    style={{ filter: `drop-shadow(0 0 8px ${hue}60)`, transition: 'stroke-dashoffset 1.5s cubic-bezier(0.34,1.56,0.64,1)' }}
                />
            </svg>
            <div className="text-center z-10">
                <div className="text-2xl font-bold font-display" style={{ color: hue }}>
                    <Counter value={score} />
                </div>
                <div className="text-[10px] text-text-3 font-mono uppercase tracking-widest mt-0.5">Debt Score</div>
            </div>
            <div className="absolute -inset-2 rounded-full animate-pulse-ring" style={{ border: `1px solid ${hue}30` }} />
        </div>
    );
}

/* ── Metric Card ─────────────────────────────────────────────────────── */
function MetricCard({
    label, value, icon: Icon, color = '#00F5A0', trend, sublabel
}: {
    label: string; value: number | string; icon: any; color?: string; trend?: 'up' | 'down' | null; sublabel?: string;
}) {
    const ref = useRef<HTMLDivElement>(null);
    const handleMouseMove = (e: React.MouseEvent) => {
        if (!ref.current) return;
        const rect = ref.current.getBoundingClientRect();
        ref.current.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
        ref.current.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
    };

    return (
        <div
            ref={ref}
            onMouseMove={handleMouseMove}
            className="glass-card rounded-2xl p-5 spotlight relative overflow-hidden group"
        >
            <div className="relative z-10">
                <div className="flex items-start justify-between mb-3">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${color}15`, border: `1px solid ${color}25` }}>
                        <Icon className="w-4 h-4" style={{ color }} />
                    </div>
                    {trend && (
                        <div className={cn('flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full',
                            trend === 'up' ? 'bg-sev-critical-bg text-sev-critical' : 'bg-sev-low-bg text-sev-low'
                        )}>
                            {trend === 'up' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        </div>
                    )}
                </div>
                <div className="text-2xl font-bold font-display text-text-1">
                    {typeof value === 'number' ? <Counter value={value} /> : value}
                </div>
                <div className="text-xs text-text-3 mt-1">{label}</div>
                {sublabel && <div className="text-[10px] text-text-3/60 mt-0.5">{sublabel}</div>}
            </div>
            <div className="absolute bottom-0 right-0 w-16 h-16 rounded-full opacity-5 blur-xl" style={{ background: color }} />
        </div>
    );
}

/* ── Scan Row ────────────────────────────────────────────────────────── */
function ScanRow({ scan, index }: { scan: Scan; index: number }) {
    const statusColors: Record<string, string> = {
        completed: '#00F5A0', running: '#FFD60A', failed: '#FF2D55', queued: '#6B7280'
    };
    const color = statusColors[scan.status] ?? '#6B7280';
    const repoName = (scan.repo_url ?? '').split('/').pop() || scan.id.slice(0, 8);

    return (
        <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
        >
            <Link href={`/scans/${scan.id}/issues`} className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-bg-card-2 transition-all group">
                <div className="w-2 h-2 rounded-full flex-shrink-0 animate-glow-pulse" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
                <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-text-1 truncate font-mono">{repoName}</p>
                    <p className="text-[10px] text-text-3 capitalize">{scan.status} · {scan.branch}</p>
                </div>
                {scan.summary?.total_issues !== undefined && (
                    <span className="text-[10px] font-mono text-text-2 flex-shrink-0">
                        {scan.summary.total_issues} issues
                    </span>
                )}
                <ChevronRight className="w-3 h-3 text-text-3 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </Link>
        </motion.div>
    );
}

/* ── Mini Chart ──────────────────────────────────────────────────────── */
function SparkLine({ data, color }: { data: number[]; color: string }) {
    const chartData = data.map((v, i) => ({ v, i }));
    return (
        <ResponsiveContainer width="100%" height={40}>
            <AreaChart data={chartData}>
                <defs>
                    <linearGradient id={`g${color.replace('#','')}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={color} stopOpacity={0} />
                    </linearGradient>
                </defs>
                <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.5} fill={`url(#g${color.replace('#','')})`} dot={false} />
            </AreaChart>
        </ResponsiveContainer>
    );
}

/* ── AI Insight Ticker ───────────────────────────────────────────────── */
const INSIGHTS = [
    '⚡ 3 quick wins can be fixed in under 30 minutes',
    '🔴 2 critical security vulnerabilities detected',
    '📈 Debt score improved 12% this week',
    '🤖 AI generated 10 auto-fix proposals ready',
    '🔀 PR Guardian blocked 1 high-debt commit today',
];

function InsightTicker() {
    const [idx, setIdx] = useState(0);
    useEffect(() => {
        const t = setInterval(() => setIdx(p => (p + 1) % INSIGHTS.length), 4000);
        return () => clearInterval(t);
    }, []);
    return (
        <AnimatePresence mode="wait">
            <motion.p
                key={idx}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.3 }}
                className="text-xs text-text-2"
            >
                {INSIGHTS[idx]}
            </motion.p>
        </AnimatePresence>
    );
}

/* ── Main Dashboard ──────────────────────────────────────────────────── */
export default function DashboardPage() {
    const router = useRouter();
    const user = useAuthStore((s) => s.user);
    const org: string | null = null; // org from API query below
    useDashboardWS(org);

    const { data: scansData, isLoading } = useScans({ limit: 5 });
    const { data: latestScan } = useLatestScan();
    const { data: billing } = useBilling();

    const { data: analytics } = useQuery({
        queryKey: ['analytics', 'stats'],
        queryFn: () => request<any>('/api/v1/analytics/stats?days=30'),
        staleTime: 60_000,
    });

    const scans = scansData?.scans ?? [];
    const debtScore = latestScan?.debt_score ?? latestScan?.summary?.total_issues ?? 0;
    const totalIssues = analytics?.total_issues ?? latestScan?.summary?.total_issues ?? 0;
    const fixesGenerated = analytics?.fixes_generated ?? 0;
    const prsCreated = analytics?.prs_created ?? 0;

    const trendData = [12, 18, 14, 22, 19, 25, 21, 28, 24, 31, 27, 35];

    const firstName = user?.name?.split(' ')[0] ?? 'there';

    return (
        <div className="min-h-screen relative">
            {/* Background grid */}
            <div className="fixed inset-0 bg-grid opacity-100 pointer-events-none" />
            <div className="fixed inset-0 bg-radial-brand pointer-events-none" />

            <div className="relative z-10 p-6 max-w-7xl mx-auto space-y-6">

                {/* ── Header ──────────────────────────────────────────── */}
                <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold font-display">
                            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 17 ? 'afternoon' : 'evening'},{' '}
                            <span className="gradient-brand">{firstName}</span>
                        </h1>
                        <p className="text-sm text-text-3 mt-1">
                            {scans.length > 0
                                ? `${scans.filter(s => s.status === 'completed').length} scans completed · Last scan ${latestScan ? 'just now' : 'never'}`
                                : 'Run your first scan to see insights'}
                        </p>
                    </div>
                    <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
                        <Link
                            href="/scans/new"
                            className="flex items-center gap-2 h-10 px-5 rounded-xl text-sm font-medium text-bg-base transition-all"
                            style={{ background: 'linear-gradient(135deg, #00F5A0 0%, #00D9FF 100%)', boxShadow: '0 0 20px rgba(0,245,160,0.3)' }}
                        >
                            <Play className="w-3.5 h-3.5 fill-current" />
                            Run Scan
                        </Link>
                    </motion.div>
                </motion.div>

                {/* ── Ticker ──────────────────────────────────────────── */}
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.1 }}
                    className="glass-card rounded-xl px-4 py-2.5 flex items-center gap-3"
                >
                    <div className="flex items-center gap-1.5 shrink-0">
                        <div className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" />
                        <span className="text-[10px] font-mono text-brand uppercase tracking-widest">AI Live</span>
                    </div>
                    <div className="w-px h-4 bg-border" />
                    <InsightTicker />
                </motion.div>

                {/* ── Bento Grid ──────────────────────────────────────── */}
                <div className="grid grid-cols-12 gap-4 auto-rows-auto">

                    {/* Debt Score — tall left cell */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: 0.15 }}
                        className="col-span-12 md:col-span-4 glass-card rounded-2xl p-6 flex flex-col items-center justify-center gap-4 relative overflow-hidden"
                        style={{ minHeight: '220px' }}
                    >
                        <div className="absolute inset-0 bg-dot opacity-30" />
                        <DebtRing score={debtScore} />
                        <div className="text-center">
                            <p className="text-xs text-text-3 font-mono uppercase tracking-wider">
                                {latestScan ? `${latestScan.branch ?? 'main'} branch` : 'No scans yet'}
                            </p>
                            {latestScan && (
                                <Link
                                    href={`/scans/${latestScan.id}/issues`}
                                    className="mt-2 inline-flex items-center gap-1 text-[11px] text-brand hover:text-brand-light transition-colors"
                                >
                                    View issues <ArrowRight className="w-3 h-3" />
                                </Link>
                            )}
                        </div>
                    </motion.div>

                    {/* Metrics 2x2 */}
                    <div className="col-span-12 md:col-span-8 grid grid-cols-2 gap-4">
                        {[
                            { label: 'Total Issues', value: totalIssues, icon: AlertTriangle, color: '#FF6B35', trend: totalIssues > 100 ? 'up' as const : 'down' as const },
                            { label: 'Fixes Generated', value: fixesGenerated, icon: Wrench, color: '#00F5A0', sublabel: 'AI-powered' },
                            { label: 'PRs Created', value: prsCreated, icon: GitPullRequest, color: '#00D9FF', sublabel: 'Auto-merged' },
                            { label: 'Scans Run', value: scansData?.total ?? 0, icon: Activity, color: '#8B5CF6', sublabel: '30 days' },
                        ].map((m, i) => (
                            <motion.div key={m.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.05 }}>
                                <MetricCard {...m} />
                            </motion.div>
                        ))}
                    </div>

                    {/* Severity breakdown */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.35 }}
                        className="col-span-12 md:col-span-5 glass-card rounded-2xl p-5"
                    >
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-sm font-semibold font-display text-text-1">Issue Breakdown</h3>
                            <span className="text-[10px] font-mono text-text-3 uppercase tracking-wider">By Severity</span>
                        </div>
                        {[
                            { label: 'Critical', count: latestScan?.summary?.critical ?? 0, color: '#FF2D55', width: `${Math.min((latestScan?.summary?.critical ?? 0) / Math.max(totalIssues, 1) * 100, 100)}%` },
                            { label: 'High', count: latestScan?.summary?.high ?? 0, color: '#FF6B35', width: `${Math.min((latestScan?.summary?.high ?? 0) / Math.max(totalIssues, 1) * 100, 100)}%` },
                            { label: 'Medium', count: latestScan?.summary?.medium ?? 0, color: '#FFD60A', width: `${Math.min((latestScan?.summary?.medium ?? 0) / Math.max(totalIssues, 1) * 100, 100)}%` },
                            { label: 'Low', count: latestScan?.summary?.low ?? 0, color: '#00F5A0', width: `${Math.min((latestScan?.summary?.low ?? 0) / Math.max(totalIssues, 1) * 100, 100)}%` },
                        ].map((s, i) => (
                            <div key={s.label} className="mb-3">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-text-2">{s.label}</span>
                                    <span className="text-xs font-mono font-medium" style={{ color: s.color }}>{s.count}</span>
                                </div>
                                <div className="h-1.5 bg-bg-card-2 rounded-full overflow-hidden">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: s.width }}
                                        transition={{ delay: 0.4 + i * 0.1, duration: 0.8, ease: [0.34, 1.56, 0.64, 1] }}
                                        className="h-full rounded-full"
                                        style={{ background: s.color, boxShadow: `0 0 8px ${s.color}60` }}
                                    />
                                </div>
                            </div>
                        ))}
                    </motion.div>

                    {/* Trend chart */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.4 }}
                        className="col-span-12 md:col-span-7 glass-card rounded-2xl p-5"
                    >
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="text-sm font-semibold font-display text-text-1">Debt Trend</h3>
                            <span className="text-[10px] font-mono text-brand">↓ 12% this week</span>
                        </div>
                        <SparkLine data={trendData} color="#00F5A0" />
                        <div className="flex items-center gap-4 mt-2">
                            <div className="flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-full bg-brand" />
                                <span className="text-[10px] text-text-3">Issues over time</span>
                            </div>
                        </div>
                    </motion.div>

                    {/* Recent scans */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.45 }}
                        className="col-span-12 md:col-span-6 glass-card rounded-2xl p-5"
                    >
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-semibold font-display text-text-1">Recent Scans</h3>
                            <Link href="/scans" className="text-[11px] text-brand hover:text-brand-light transition-colors flex items-center gap-1">
                                View all <ChevronRight className="w-3 h-3" />
                            </Link>
                        </div>
                        <div className="space-y-0.5">
                            {isLoading ? (
                                Array.from({ length: 3 }).map((_, i) => (
                                    <div key={i} className="h-10 rounded-xl bg-bg-card-2 animate-shimmer" style={{ backgroundImage: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.03) 50%, transparent 100%)', backgroundSize: '200% 100%' }} />
                                ))
                            ) : scans.length === 0 ? (
                                <div className="py-6 text-center">
                                    <p className="text-xs text-text-3">No scans yet</p>
                                    <Link href="/scans/new" className="text-xs text-brand mt-1 inline-block hover:text-brand-light transition-colors">
                                        Run your first scan →
                                    </Link>
                                </div>
                            ) : (
                                scans.map((scan, i) => <ScanRow key={scan.id} scan={scan} index={i} />)
                            )}
                        </div>
                    </motion.div>

                    {/* Quick actions */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.5 }}
                        className="col-span-12 md:col-span-6 glass-card rounded-2xl p-5"
                    >
                        <h3 className="text-sm font-semibold font-display text-text-1 mb-3">Quick Actions</h3>
                        <div className="grid grid-cols-2 gap-2">
                            {[
                                { label: 'New Scan', icon: Play, href: '/scans/new', color: '#00F5A0', desc: 'Analyze a repo' },
                                { label: 'View Issues', icon: AlertTriangle, href: latestScan ? `/scans/${latestScan.id}/issues` : '/scans', color: '#FF6B35', desc: 'Browse all debt' },
                                { label: 'Autopilot', icon: Cpu, href: latestScan ? `/scans/${latestScan.id}/autopilot` : '/scans', color: '#8B5CF6', desc: 'AI auto-fix' },
                                { label: 'Analytics', icon: BarChart2, href: '/analytics', color: '#00D9FF', desc: 'Trends & reports' },
                            ].map((a) => (
                                <Link
                                    key={a.label}
                                    href={a.href as any}
                                    className="flex flex-col gap-2 p-3 rounded-xl border border-border hover:border-opacity-50 bg-bg-card hover:bg-bg-card-hover transition-all group"
                                    style={{ '--hover-border': a.color } as any}
                                >
                                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${a.color}15` }}>
                                        <a.icon className="w-3.5 h-3.5" style={{ color: a.color }} />
                                    </div>
                                    <div>
                                        <p className="text-xs font-medium text-text-1">{a.label}</p>
                                        <p className="text-[10px] text-text-3">{a.desc}</p>
                                    </div>
                                </Link>
                            ))}
                        </div>
                    </motion.div>

                </div>

                {/* ── Plan usage ──────────────────────────────────────── */}
                {billing && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.55 }}
                        className="glass-card rounded-2xl p-4 flex items-center gap-4"
                    >
                        <div className="flex-1">
                            <div className="flex items-center justify-between mb-1.5">
                                <span className="text-xs text-text-2">
                                    <span className="text-brand font-medium">{billing.scans_used}</span>
                                    <span className="text-text-3">/{billing.scans_limit} scans</span>
                                </span>
                                <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full" style={{ background: 'rgba(0,245,160,0.1)', color: '#00F5A0' }}>
                                    {billing.plan}
                                </span>
                            </div>
                            <div className="h-1 bg-bg-card-2 rounded-full overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all duration-700"
                                    style={{
                                        width: `${Math.min((billing.scans_used / billing.scans_limit) * 100, 100)}%`,
                                        background: 'linear-gradient(90deg, #00F5A0, #00D9FF)'
                                    }}
                                />
                            </div>
                        </div>
                        {billing.plan === 'free' && (
                            <Link
                                href="/settings/billing"
                                className="text-[11px] text-text-2 hover:text-brand transition-colors whitespace-nowrap flex items-center gap-1"
                            >
                                Upgrade <Star className="w-3 h-3" />
                            </Link>
                        )}
                    </motion.div>
                )}
            </div>
        </div>
    );
}
