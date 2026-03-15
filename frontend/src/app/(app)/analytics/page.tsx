'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { BarChart3, TrendingUp, AlertTriangle, GitPullRequest } from 'lucide-react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar,
    PieChart, Pie, Cell,
} from 'recharts';

import { getAnalyticsStats } from '@/lib/api/analytics';
import { MetricCard } from '@/components/ui/MetricCard';
import { SkeletonCard } from '@/components/ui/SkeletonCard';
import { cn } from '@/lib/utils/cn';

const TIME_RANGES = [
    { label: '7d', value: 7 },
    { label: '30d', value: 30 },
    { label: '90d', value: 90 },
    { label: 'All', value: 1000 },
];

export default function AnalyticsPage() {
    const [days, setDays] = useState(30);

    const { data: stats, isLoading } = useQuery({
        queryKey: ['analytics', 'stats', days],
        queryFn: () => getAnalyticsStats(days),
    });

    if (isLoading || !stats) {
        return (
            <div className="space-y-6 max-w-[1200px]">
                <div className="flex items-center justify-between">
                    <h1 className="text-lg font-semibold text-text-1">Analytics</h1>
                    <div className="flex bg-bg-card border border-border rounded-lg p-0.5" />
                </div>
                <div className="grid grid-cols-4 gap-4">
                    {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
                <div className="grid grid-cols-2 gap-4">
                    <SkeletonCard className="h-80" />
                    <SkeletonCard className="h-80" />
                </div>
                <SkeletonCard className="h-80 w-full" />
            </div>
        );
    }

    // Prepare chart data
    const categoryData = Object.entries(stats.category_breakdown)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value);

    const severityData = [
        { name: 'CRITICAL', value: stats.severity_breakdown.CRITICAL, color: 'var(--chart-5)' },
        { name: 'HIGH', value: stats.severity_breakdown.HIGH, color: 'var(--chart-4)' },
        { name: 'MEDIUM', value: stats.severity_breakdown.MEDIUM, color: 'var(--chart-3)' },
        { name: 'LOW', value: stats.severity_breakdown.LOW, color: 'var(--chart-1)' },
    ].filter((d) => d.value > 0);

    const CustomTooltip = ({ active, payload, label }: any) => {
        if (active && payload && payload.length) {
            return (
                <div className="bg-bg-card border border-border p-3 rounded-lg shadow-xl text-xs">
                    <p className="font-semibold text-text-1 mb-1">{label || payload[0].payload.name}</p>
                    {payload.map((entry: any, index: number) => (
                        <div key={index} className="flex items-center gap-2 mt-1">
                            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                            <span className="text-text-2 capitalize">{entry.name}:</span>
                            <span className="text-text-1 font-mono">{entry.value}</span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-6 max-w-[1200px]">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-text-1">Analytics</h1>

                {/* Date range picker */}
                <div className="flex bg-bg-card border border-border rounded-lg p-0.5">
                    {TIME_RANGES.map((range) => (
                        <button
                            key={range.value}
                            onClick={() => setDays(range.value)}
                            className={cn(
                                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                                days === range.value
                                    ? 'bg-bg-elevated text-text-1 shadow-sm border border-border/50'
                                    : 'text-text-3 hover:text-text-2',
                            )}
                        >
                            {range.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Metric cards */}
            <div className="grid grid-cols-4 gap-4">
                <MetricCard label="Scans Run" value={stats.scans_run} icon={BarChart3} color="text-brand" />
                <MetricCard label="Issues Found" value={stats.total_issues} icon={AlertTriangle} color="text-accent-amber" />
                <MetricCard label="Fixes Generated" value={stats.fixes_generated} icon={GitPullRequest} color="text-accent-cyan" />
                <MetricCard label="PRs Created" value={stats.prs_created} icon={TrendingUp} color="text-accent-violet" />
            </div>

            {/* Top Charts */}
            <div className="grid grid-cols-2 gap-4 h-80">
                {/* Category Bar Chart */}
                <div className="bg-bg-card border border-border rounded-xl p-5 flex flex-col">
                    <h3 className="text-xs font-semibold text-text-2 mb-4 shrink-0">Issues by Category</h3>
                    <div className="flex-1 min-h-0">
                        {categoryData.every((d) => d.value === 0) ? (
                            <div className="h-full flex items-center justify-center text-xs text-text-3">No data available</div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={categoryData} layout="vertical" margin={{ top: 0, right: 0, left: 30, bottom: 0 }}>
                                    <XAxis type="number" hide />
                                    <YAxis
                                        dataKey="name"
                                        type="category"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: 'var(--text-3)', fontSize: 11 }}
                                    />
                                    <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--bg-card-2)' }} />
                                    <Bar dataKey="value" fill="var(--chart-2)" radius={[0, 4, 4, 0]} barSize={20} />
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>

                {/* Severity Pie Chart */}
                <div className="bg-bg-card border border-border rounded-xl p-5 flex flex-col">
                    <h3 className="text-xs font-semibold text-text-2 mb-4 shrink-0">Severity Distribution</h3>
                    <div className="flex-1 min-h-0">
                        {severityData.length === 0 ? (
                            <div className="h-full flex items-center justify-center text-xs text-text-3">No data available</div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={severityData}
                                        dataKey="value"
                                        nameKey="name"
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={60}
                                        outerRadius={100}
                                        stroke="none"
                                        paddingAngle={2}
                                    >
                                        {severityData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip content={<CustomTooltip />} />
                                </PieChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </div>

            {/* Debt Trend Chart */}
            <div className="bg-bg-card border border-border rounded-xl p-5 h-80 flex flex-col">
                <h3 className="text-xs font-semibold text-text-2 mb-4 shrink-0">Debt Score Trend</h3>
                <div className="flex-1 min-h-0">
                    {stats.debt_trend.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-xs text-text-3">No trend data available</div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={stats.debt_trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorDebt" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-default)" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: 'var(--text-3)', fontSize: 11 }}
                                    dy={10}
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: 'var(--text-3)', fontSize: 11 }}
                                    domain={['dataMin - 10', 'dataMax + 10']}
                                />
                                <Tooltip content={<CustomTooltip />} />
                                <Area
                                    type="monotone"
                                    dataKey="debt_score"
                                    name="Debt Score"
                                    stroke="var(--chart-1)"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorDebt)"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </div>
        </motion.div>
    );
}
