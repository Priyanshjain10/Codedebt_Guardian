'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import {
    LayoutDashboard,
    FolderGit2,
    ScanSearch,
    AlertTriangle,
    Wrench,
    Bot,
    Shield,
    BarChart3,
    Settings,
    Zap,
    ChevronsLeft,
    ChevronsRight,
} from 'lucide-react';
import { useUIStore } from '@/store/uiStore';
import { useBilling } from '@/lib/hooks/useBilling';
import { useAuthStore } from '@/store/authStore';
import { useLatestScan } from '@/lib/hooks/useScans';
import { cn } from '@/lib/utils/cn';
const NAV_ITEMS = [
    { id: 'dashboard', href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'projects', href: '/projects', label: 'Projects', icon: FolderGit2 },
    { id: 'scans', href: '/scans', label: 'Scans', icon: ScanSearch },
    { id: 'issues', href: '/scans/:latest/issues', label: 'Issues', icon: AlertTriangle },
    { id: 'fixes', href: '/scans/:latest/fixes', label: 'Fixes', icon: Wrench },
    { id: 'autopilot', href: '/scans/:latest/autopilot', label: 'Autopilot', icon: Bot },
    { id: 'pr-guardian', href: '/scans/:latest/pr-guardian', label: 'PR Guardian', icon: Shield },
    { id: 'analytics', href: '/analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'settings', href: '/settings', label: 'Settings', icon: Settings },
] as const;

export function Sidebar() {
    const pathname = usePathname();
    const { sidebarCollapsed, toggleSidebar } = useUIStore();
    const { data: billing } = useBilling();
    const user = useAuthStore((s) => s.user);
    const { data: latestScan, isError } = useLatestScan();

    const scanUsed = billing?.scans_used ?? 0;
    const scanLimit = billing?.scans_limit ?? 5;
    const plan = billing?.plan ?? 'free';
    const pct = scanLimit > 0 ? Math.min((scanUsed / scanLimit) * 100, 100) : 0;

    return (
        <aside
            className={cn(
                'h-screen flex flex-col bg-bg-elevated border-r border-border transition-all duration-200 shrink-0',
                sidebarCollapsed ? 'w-16' : 'w-60',
            )}
        >
            {/* Logo */}
            <div className="h-12 flex items-center gap-2 px-4 border-b border-border shrink-0">
                <div className="w-7 h-7 rounded-lg bg-brand/20 flex items-center justify-center shrink-0">
                    <Zap className="w-4 h-4 text-brand" />
                </div>
                {!sidebarCollapsed && (
                    <span className="text-sm font-semibold text-text-1 truncate">CodeDebt Guardian</span>
                )}
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto scrollbar-thin">
                {NAV_ITEMS.map((item) => {
                    let href: string = item.href;
                    if (item.href.includes(':latest')) {
                        href = latestScan ? item.href.replace(':latest', latestScan.id) : '/scans/new';
                    }

                    const isActive = pathname.startsWith(href) && href !== '/scans/new';
                    const Icon = item.icon;
                    return (
                        <Link
                            key={item.id}
                            href={href as any}
                            title={href === '/scans/new' && item.href.includes(':latest') ? 'Run your first scan' : undefined}
                            className={cn(
                                'flex items-center gap-3 h-9 px-3 rounded-lg text-sm transition-colors',
                                isActive
                                    ? 'bg-brand-dim text-brand-light font-medium'
                                    : 'text-text-2 hover:text-text-1 hover:bg-bg-card-2',
                            )}
                        >
                            <Icon className="w-4 h-4 shrink-0" />
                            {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
                        </Link>
                    );
                })}
            </nav>

            {/* Bottom section */}
            <div className="px-3 pb-3 space-y-3 border-t border-border pt-3 shrink-0">
                {/* Plan badge + usage */}
                {!sidebarCollapsed && (
                    <div className="px-2">
                        <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[10px] font-bold tracking-wider uppercase text-text-3">
                                {plan}
                            </span>
                            <span className="text-[10px] text-text-3">
                                {scanUsed}/{scanLimit} scans
                            </span>
                        </div>
                        <div className="h-1 rounded-full bg-bg-card overflow-hidden">
                            <motion.div
                                className="h-full rounded-full bg-brand"
                                initial={{ width: 0 }}
                                animate={{ width: `${pct}%` }}
                                transition={{ duration: 0.5, ease: 'easeOut' }}
                            />
                        </div>
                    </div>
                )}

                {/* User info */}
                {user && (
                    <div className="flex items-center gap-2 px-2">
                        <div className="w-7 h-7 rounded-full bg-brand/20 flex items-center justify-center shrink-0">
                            <span className="text-xs font-medium text-brand">
                                {user.name?.charAt(0)?.toUpperCase() ?? 'U'}
                            </span>
                        </div>
                        {!sidebarCollapsed && (
                            <div className="min-w-0">
                                <p className="text-xs font-medium text-text-1 truncate">{user.name}</p>
                                <p className="text-[10px] text-text-3 truncate">{user.email}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Collapse toggle */}
                <button
                    onClick={toggleSidebar}
                    className="flex items-center justify-center w-full h-7 rounded-lg text-text-3 hover:text-text-2 hover:bg-bg-card-2 transition-colors"
                    aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                >
                    {sidebarCollapsed ? (
                        <ChevronsRight className="w-4 h-4" />
                    ) : (
                        <ChevronsLeft className="w-4 h-4" />
                    )}
                </button>
            </div>
        </aside>
    );
}
