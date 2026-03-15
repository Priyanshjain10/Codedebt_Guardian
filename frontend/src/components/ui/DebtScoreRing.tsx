'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils/cn';

interface DebtScoreRingProps {
    score: number;
    grade?: string;
    size?: number;
    strokeWidth?: number;
    animated?: boolean;
    showLabel?: boolean;
    className?: string;
}

function getColor(score: number): string {
    if (score <= 30) return 'var(--sev-low)';
    if (score <= 60) return 'var(--sev-medium)';
    if (score <= 80) return 'var(--sev-high)';
    return 'var(--sev-critical)';
}

export function DebtScoreRing({
    score,
    grade,
    size = 100,
    strokeWidth = 6,
    animated = true,
    showLabel = true,
    className,
}: DebtScoreRingProps) {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const pct = Math.min(score, 100) / 100;
    const target = circumference * (1 - pct);
    const color = getColor(score);

    const [offset, setOffset] = useState(animated ? circumference : target);

    useEffect(() => {
        if (animated) {
            const timer = setTimeout(() => setOffset(target), 100);
            return () => clearTimeout(timer);
        }
    }, [target, animated, circumference]);

    return (
        <div className={cn('relative inline-flex items-center justify-center', className)} style={{ width: size, height: size }}>
            <svg width={size} height={size} className="-rotate-90">
                {/* Background track */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="var(--border-subtle)"
                    strokeWidth={strokeWidth}
                />
                {/* Value arc */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={color}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    style={{
                        transition: animated ? 'stroke-dashoffset 1s ease-out' : 'none',
                    }}
                />
            </svg>
            {showLabel && (
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-lg font-bold" style={{ color }}>
                        {Math.round(score)}
                    </span>
                    {grade && (
                        <span className="text-[10px] font-medium text-text-3 uppercase tracking-wider">
                            {grade}
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}
