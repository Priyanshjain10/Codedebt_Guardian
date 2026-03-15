'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
    label: string;
    value: number;
    icon: LucideIcon;
    subtitle?: string;
    trend?: string;
    color?: string;
    className?: string;
}

export function MetricCard({ label, value, icon: Icon, subtitle, trend, color = 'text-brand', className }: MetricCardProps) {
    const [displayed, setDisplayed] = useState(0);

    useEffect(() => {
        const duration = 800;
        const start = performance.now();
        const animate = (now: number) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setDisplayed(Math.round(value * eased));
            if (progress < 1) requestAnimationFrame(animate);
        };
        requestAnimationFrame(animate);
    }, [value]);

    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                'bg-bg-card border border-border rounded-xl p-4 hover:border-border-strong transition-colors',
                className,
            )}
        >
            <div className="flex items-start justify-between mb-3">
                <span className="text-xs font-medium text-text-2">{label}</span>
                <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', 'bg-brand-dim')}>
                    <Icon className={cn('w-4 h-4', color)} />
                </div>
            </div>
            <div className="flex items-baseline gap-2">
                <span className={cn('text-2xl font-bold font-mono', color)}>
                    {displayed.toLocaleString()}
                </span>
                {trend && (
                    <span className="text-xs text-brand">
                        {trend}
                    </span>
                )}
            </div>
            {subtitle && (
                <p className="text-xs text-text-3 mt-1">{subtitle}</p>
            )}
        </motion.div>
    );
}
