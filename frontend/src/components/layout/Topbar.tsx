'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, Plus, Bell, Github } from 'lucide-react';
import { useUIStore } from '@/store/uiStore';

export function Topbar() {
    const pathname = usePathname();
    const setCommandPalette = useUIStore((s) => s.setCommandPalette);

    // Build breadcrumbs from pathname
    const segments = pathname.split('/').filter(Boolean);
    const breadcrumbs = segments.map((seg, i) => ({
        label: seg.charAt(0).toUpperCase() + seg.slice(1),
        href: '/' + segments.slice(0, i + 1).join('/'),
    }));

    return (
        <header className="h-12 flex items-center justify-between px-4 border-b border-border bg-bg-elevated shrink-0">
            {/* Left: Breadcrumbs */}
            <nav className="flex items-center gap-1 text-sm">
                <Link href="/dashboard" className="text-text-3 hover:text-text-2 transition-colors">
                    Home
                </Link>
                {breadcrumbs.map((bc) => (
                    <span key={bc.href} className="flex items-center gap-1">
                        <span className="text-text-3">/</span>
                        <Link href={bc.href} className="text-text-2 hover:text-text-1 transition-colors capitalize">
                            {bc.label}
                        </Link>
                    </span>
                ))}
            </nav>

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
                {/* Global Search */}
                <button
                    onClick={() => setCommandPalette(true)}
                    className="flex items-center gap-2 h-8 px-3 rounded-lg bg-bg-card border border-border text-text-3 hover:text-text-2 hover:border-border-strong transition-colors text-xs"
                >
                    <Search className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Search...</span>
                    <kbd className="hidden sm:inline text-[10px] px-1.5 py-0.5 rounded bg-bg-base border border-border font-mono">
                        ⌘K
                    </kbd>
                </button>

                {/* GitHub status */}
                <Link
                    href="/settings/github"
                    className="flex items-center gap-1.5 h-8 px-2.5 rounded-lg text-xs text-text-2 hover:text-text-1 hover:bg-bg-card-2 transition-colors"
                >
                    <Github className="w-3.5 h-3.5" />
                    <span className="hidden md:inline">GitHub</span>
                </Link>

                {/* Notifications */}
                <button
                    className="relative w-8 h-8 rounded-lg flex items-center justify-center text-text-3 hover:text-text-2 hover:bg-bg-card-2 transition-colors"
                    aria-label="Notifications"
                >
                    <Bell className="w-4 h-4" />
                </button>

                {/* Run New Scan */}
                <Link
                    href="/scans/new"
                    className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors"
                >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Run Scan</span>
                </Link>
            </div>
        </header>
    );
}
