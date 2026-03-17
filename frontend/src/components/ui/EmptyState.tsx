'use client';

import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils/cn';

interface EmptyStateProps {
    icon: LucideIcon;
    title: string;
    description: string;
    action?: {
        label: string;
        onClick: () => void;
    };
    className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
    return (
        <div className={cn('flex flex-col items-center justify-center py-16 text-center', className)}>
            <div className="w-12 h-12 rounded-xl bg-bg-card-2 flex items-center justify-center mb-4">
                <Icon className="w-6 h-6 text-text-3" />
            </div>
            <h3 className="text-sm font-medium text-text-1 mb-1">{title}</h3>
            <p className="text-xs text-text-3 max-w-xs mb-4">{description}</p>
            {action && (
                <button
                    onClick={action.onClick}
                    className="h-8 px-4 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors"
                >
                    {action.label}
                </button>
            )}
        </div>
    );
}
