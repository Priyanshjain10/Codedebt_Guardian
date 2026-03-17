'use client';

import { cn } from '@/lib/utils/cn';

export function SkeletonCard({ className }: { className?: string }) {
    return (
        <div className={cn('bg-bg-card border border-border rounded-xl p-4 animate-pulse', className)}>
            <div className="flex items-start justify-between mb-3">
                <div className="h-3 w-20 bg-bg-card-2 rounded" />
                <div className="w-8 h-8 bg-bg-card-2 rounded-lg" />
            </div>
            <div className="h-7 w-16 bg-bg-card-2 rounded mb-1" />
            <div className="h-3 w-24 bg-bg-card-2 rounded" />
        </div>
    );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
    return (
        <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
            <div className="h-10 bg-bg-card-2 border-b border-border" />
            {Array.from({ length: rows }).map((_, i) => (
                <div key={i} className="h-12 px-4 flex items-center gap-4 border-b border-border last:border-0 animate-pulse">
                    <div className="h-3 w-24 bg-bg-card-2 rounded" />
                    <div className="h-3 w-32 bg-bg-card-2 rounded" />
                    <div className="h-3 w-16 bg-bg-card-2 rounded" />
                    <div className="flex-1" />
                    <div className="h-3 w-12 bg-bg-card-2 rounded" />
                </div>
            ))}
        </div>
    );
}
