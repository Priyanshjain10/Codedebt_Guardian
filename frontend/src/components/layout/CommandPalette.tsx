'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Command } from 'cmdk';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, ScanSearch, FolderGit2, BarChart3, Settings, Plus, Zap, Github } from 'lucide-react';
import { useUIStore } from '@/store/uiStore';

const ACTIONS = [
    { id: 'new-scan', label: 'Run New Scan', icon: Plus, href: '/scans/new' },
    { id: 'dashboard', label: 'Go to Dashboard', icon: Zap, href: '/dashboard' },
    { id: 'scans', label: 'View All Scans', icon: ScanSearch, href: '/scans' },
    { id: 'projects', label: 'View Projects', icon: FolderGit2, href: '/projects' },
    { id: 'analytics', label: 'View Analytics', icon: BarChart3, href: '/analytics' },
    { id: 'github', label: 'Connect GitHub', icon: Github, href: '/settings/github' },
    { id: 'settings', label: 'Open Settings', icon: Settings, href: '/settings' },
] as const;

export function CommandPalette() {
    const router = useRouter();
    const { commandPaletteOpen, setCommandPalette } = useUIStore();
    const [search, setSearch] = useState('');

    // CMD+K shortcut
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setCommandPalette(!commandPaletteOpen);
            }
            if (e.key === 'Escape') {
                setCommandPalette(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [commandPaletteOpen, setCommandPalette]);

    const handleSelect = (href: string) => {
        setCommandPalette(false);
        setSearch('');
        router.push(href);
    };

    return (
        <AnimatePresence>
            {commandPaletteOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
                        onClick={() => setCommandPalette(false)}
                    />

                    {/* Dialog */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.96 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.96 }}
                        transition={{ duration: 0.15 }}
                        className="fixed top-[20%] left-1/2 -translate-x-1/2 z-50 w-full max-w-lg"
                    >
                        <Command
                            className="bg-bg-card border border-border rounded-xl shadow-2xl overflow-hidden"
                            shouldFilter
                        >
                            <div className="flex items-center px-4 border-b border-border">
                                <Search className="w-4 h-4 text-text-3 shrink-0" />
                                <Command.Input
                                    value={search}
                                    onValueChange={setSearch}
                                    placeholder="Search repositories, issues, or actions..."
                                    className="flex-1 h-11 px-3 text-sm bg-transparent text-text-1 placeholder:text-text-3 focus:outline-none"
                                />
                                <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-bg-base border border-border text-text-3 font-mono">
                                    ESC
                                </kbd>
                            </div>

                            <Command.List className="max-h-80 overflow-y-auto scrollbar-thin p-2">
                                <Command.Empty className="px-4 py-8 text-center text-sm text-text-3">
                                    No results found
                                </Command.Empty>

                                <Command.Group heading="Actions" className="mb-2">
                                    {ACTIONS.map((action) => {
                                        const Icon = action.icon;
                                        return (
                                            <Command.Item
                                                key={action.id}
                                                value={action.label}
                                                onSelect={() => handleSelect(action.href)}
                                                className="flex items-center gap-3 h-9 px-3 rounded-lg text-sm text-text-2 cursor-pointer data-[selected=true]:bg-brand-dim data-[selected=true]:text-brand-light transition-colors"
                                            >
                                                <Icon className="w-4 h-4 shrink-0" />
                                                <span>{action.label}</span>
                                            </Command.Item>
                                        );
                                    })}
                                </Command.Group>
                            </Command.List>
                        </Command>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
