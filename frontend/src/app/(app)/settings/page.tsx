'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { Github, Key, CreditCard, Users, ChevronRight } from 'lucide-react';

const SECTIONS = [
    { href: '/settings/team', label: 'Team', desc: 'Manage organization members and roles', icon: Users },
    { href: '/settings/github', label: 'GitHub Integration', desc: 'Connect GitHub App, manage repos', icon: Github },
    { href: '/settings/api-keys', label: 'API Keys', desc: 'Create and manage API keys', icon: Key },
    { href: '/settings/billing', label: 'Billing', desc: 'View usage, manage subscription', icon: CreditCard },
] as const;

export default function SettingsPage() {
    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 max-w-[700px]">
            <h1 className="text-lg font-semibold text-text-1">Settings</h1>

            <div className="bg-bg-card border border-border rounded-xl divide-y divide-border">
                {SECTIONS.map((s) => {
                    const Icon = s.icon;
                    return (
                        <Link key={s.href} href={s.href} className="flex items-center gap-4 px-5 py-4 hover:bg-bg-card-2 transition-colors">
                            <div className="w-9 h-9 rounded-lg bg-brand-dim flex items-center justify-center shrink-0">
                                <Icon className="w-4 h-4 text-brand" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-text-1">{s.label}</p>
                                <p className="text-xs text-text-3">{s.desc}</p>
                            </div>
                            <ChevronRight className="w-4 h-4 text-text-3" />
                        </Link>
                    );
                })}
            </div>
        </motion.div>
    );
}
