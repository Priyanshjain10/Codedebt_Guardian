'use client';

import { cn } from '@/lib/utils/cn';
import { getSeverityConfig } from '@/lib/utils/severity';
import type { DebtSeverity } from '@/types/api';

interface SeverityBadgeProps {
    severity: DebtSeverity;
    className?: string;
    pulse?: boolean;
}

export function SeverityBadge({ severity, className, pulse }: SeverityBadgeProps) {
    const config = getSeverityConfig(severity);
    return (
        <span
            className={cn(
                'inline-flex items-center gap-1 text-[10px] font-bold tracking-wider uppercase rounded-sm px-1.5 py-0.5 font-mono',
                config.bg,
                config.color,
                pulse && severity === 'CRITICAL' && 'animate-pulse-slow',
                className,
            )}
        >
            <span className={cn('w-1.5 h-1.5 rounded-full', config.dot)} />
            {config.label}
        </span>
    );
}
