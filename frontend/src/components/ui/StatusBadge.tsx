'use client';

import { cn } from '@/lib/utils/cn';
import type { ScanStatus } from '@/types/api';

const STATUS_CONFIG: Record<string, { label: string; color: string; dot: string; bg: string }> = {
    completed: { label: 'Completed', color: 'text-status-completed', dot: 'bg-status-completed', bg: 'bg-status-completed/10' },
    running: { label: 'Running', color: 'text-status-running', dot: 'bg-status-running', bg: 'bg-status-running/10' },
    failed: { label: 'Failed', color: 'text-status-failed', dot: 'bg-status-failed', bg: 'bg-status-failed/10' },
    queued: { label: 'Queued', color: 'text-status-queued', dot: 'bg-status-queued', bg: 'bg-status-queued/10' },
    pending: { label: 'Pending', color: 'text-status-pending', dot: 'bg-status-pending', bg: 'bg-status-pending/10' },
};

export function StatusBadge({ status, className }: { status: ScanStatus | string; className?: string }) {
    const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.queued;
    return (
        <span
            className={cn(
                'inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider rounded-full px-2 py-0.5',
                config.bg,
                config.color,
                className,
            )}
        >
            <span
                className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    config.dot,
                    status === 'running' && 'animate-pulse',
                )}
            />
            {config.label}
        </span>
    );
}
