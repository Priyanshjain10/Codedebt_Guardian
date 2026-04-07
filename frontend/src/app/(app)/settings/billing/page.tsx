'use client';

import { motion } from 'framer-motion';
import { CreditCard, Check, ArrowUpRight, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as billingApi from '@/lib/api/billing';
import { cn } from '@/lib/utils/cn';
import { useAuthStore } from '@/store/authStore';

const PLANS = [
    {
        id: 'free', name: 'Free', price: '$0/mo',
        features: ['5 scans/month', '1 project', '1 user', 'Community support'],
        missing: ['Auto-PR creation', 'Team management', 'API access'],
    },
    {
        id: 'pro', name: 'Pro', price: '$29/mo',
        features: ['100 scans/month', 'Unlimited projects', '10 users', 'Auto-PR creation', 'API access', 'Priority support'],
        missing: [],
    },
    {
        id: 'enterprise', name: 'Enterprise', price: 'Contact us',
        features: ['Unlimited scans', 'Unlimited projects', 'Unlimited users', 'Auto-PR creation', 'API access', 'SSO & SAML', 'Dedicated support'],
        missing: [],
    },
] as const;

export default function BillingPage() {
    const [upgrading, setUpgrading] = useState<string | null>(null);

    const { data: usage } = useQuery({
        queryKey: ['billing', 'usage'],
        queryFn: () => billingApi.getUsage(),
        staleTime: 60_000,
    });

    const currentPlan = usage?.plan ?? 'free';
    const scansUsed = usage?.scans_used ?? 0;
    const scansLimit = usage?.scans_limit ?? 5;
    const pct = scansLimit > 0 ? Math.min((scansUsed / scansLimit) * 100, 100) : 0;

    const handleUpgrade = async (plan: string) => {
        setUpgrading(plan);
        try {
            const result = await billingApi.createCheckout(plan);
            window.open(result.checkout_url, '_blank');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Checkout failed');
        } finally {
            setUpgrading(null);
        }
    };

    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-6 max-w-[900px]">
            <h1 className="text-lg font-semibold text-text-1">Billing</h1>

            {/* Current usage */}
            <div className="bg-bg-card border border-border rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <span className="text-[10px] font-bold tracking-wider uppercase text-text-3">Current Plan</span>
                        <p className="text-sm font-semibold text-text-1 capitalize mt-0.5">{currentPlan}</p>
                    </div>
                    <div className="text-right">
                        <span className="text-xs text-text-3">Scans this period</span>
                        <p className="text-sm font-bold font-mono text-text-1">{scansUsed} / {scansLimit}</p>
                    </div>
                </div>
                <div className="h-2 rounded-full bg-bg-card-2 overflow-hidden">
                    <div className="h-full rounded-full bg-brand transition-all duration-500" style={{ width: `${pct}%` }} />
                </div>
                {usage?.period_end && (
                    <p className="text-[10px] text-text-3 mt-2">Resets: {new Date(usage.period_end).toLocaleDateString()}</p>
                )}
            </div>

            {/* Plan comparison */}
            <div className="grid grid-cols-3 gap-4">
                {PLANS.map((plan) => {
                    const isCurrent = plan.id === currentPlan;
                    return (
                        <div
                            key={plan.id}
                            className={cn(
                                'bg-bg-card border rounded-xl p-5 flex flex-col',
                                isCurrent ? 'border-brand' : 'border-border',
                            )}
                        >
                            {isCurrent && (
                                <span className="text-[10px] font-bold tracking-wider uppercase text-brand mb-2">Current</span>
                            )}
                            <h3 className="text-sm font-semibold text-text-1">{plan.name}</h3>
                            <p className="text-lg font-bold text-text-1 mt-1 mb-4">{plan.price}</p>

                            <div className="flex-1 space-y-2 mb-4">
                                {plan.features.map((f) => (
                                    <div key={f} className="flex items-center gap-2 text-xs text-text-2">
                                        <Check className="w-3 h-3 text-brand shrink-0" /> {f}
                                    </div>
                                ))}
                                {plan.missing.map((f) => (
                                    <div key={f} className="flex items-center gap-2 text-xs text-text-3 line-through">
                                        <span className="w-3 h-3 shrink-0" /> {f}
                                    </div>
                                ))}
                            </div>

                            {isCurrent ? (
                                <div className="h-9 rounded-lg border border-brand flex items-center justify-center text-xs font-medium text-brand">
                                    Current Plan
                                </div>
                            ) : plan.id === 'enterprise' ? (
                                <a href="mailto:hello@codedebt.dev"
                                    className="h-9 rounded-lg border border-border flex items-center justify-center gap-1 text-xs font-medium text-text-2 hover:text-text-1 transition-colors">
                                    Contact Sales <ArrowUpRight className="w-3 h-3" />
                                </a>
                            ) : (
                                <button
                                    onClick={() => handleUpgrade(plan.id)}
                                    disabled={upgrading === plan.id}
                                    className="h-9 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                                >
                                    {upgrading === plan.id ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                                    Upgrade to {plan.name}
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </motion.div>
    );
}
