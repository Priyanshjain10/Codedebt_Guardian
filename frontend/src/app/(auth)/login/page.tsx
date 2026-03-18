'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { motion } from 'framer-motion';
import { Loader2, Eye, EyeOff, Shield, ArrowRight, Zap } from 'lucide-react';
import { toast } from 'sonner';
import * as authApi from '@/lib/api/auth';
import { useAuthStore } from '@/store/authStore';

const schema = z.object({
    email: z.string().email('Valid email required'),
    password: z.string().min(6, 'At least 6 characters'),
});
type FormData = z.infer<typeof schema>;

/* ── Animated Background Nodes ───────────────────────────────────────── */
function BackgroundNodes() {
    const nodes = Array.from({ length: 20 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.random() * 3 + 1,
        duration: Math.random() * 8 + 6,
        delay: Math.random() * 4,
    }));

    return (
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {nodes.map((n) => (
                <motion.div
                    key={n.id}
                    className="absolute rounded-full"
                    style={{
                        left: `${n.x}%`,
                        top: `${n.y}%`,
                        width: n.size,
                        height: n.size,
                        background: '#00F5A0',
                        boxShadow: '0 0 6px #00F5A0',
                    }}
                    animate={{
                        opacity: [0.1, 0.5, 0.1],
                        scale: [1, 1.5, 1],
                    }}
                    transition={{
                        duration: n.duration,
                        delay: n.delay,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />
            ))}
            {/* Connection lines SVG */}
            <svg className="absolute inset-0 w-full h-full opacity-5">
                {nodes.slice(0, 8).map((n, i) => {
                    const next = nodes[(i + 1) % 8];
                    return (
                        <line
                            key={i}
                            x1={`${n.x}%`} y1={`${n.y}%`}
                            x2={`${next.x}%`} y2={`${next.y}%`}
                            stroke="#00F5A0" strokeWidth="0.5"
                        />
                    );
                })}
            </svg>
        </div>
    );
}

/* ── Feature Pill ────────────────────────────────────────────────────── */
function FeaturePill({ label, icon: Icon }: { label: string; icon: any }) {
    return (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-border bg-bg-card/50">
            <Icon className="w-3 h-3 text-brand" />
            <span className="text-[11px] text-text-2">{label}</span>
        </div>
    );
}

/* ── Main ────────────────────────────────────────────────────────────── */
export default function LoginPage() {
    const router = useRouter();
    const login = useAuthStore((s) => s.login);
    const [loading, setLoading] = useState(false);
    const [showPass, setShowPass] = useState(false);

    const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

    const onSubmit = async (data: FormData) => {
        setLoading(true);
        try {
            const tokens = await authApi.login(data);
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const meRes = await fetch(`${apiBase}/api/v1/auth/me`, {
                headers: { 'Authorization': `Bearer ${tokens.access_token}`, 'Content-Type': 'application/json' }
            });
            if (!meRes.ok) throw new Error('Failed to get user profile');
            const user = await meRes.json();
            login(tokens.access_token, user);
            router.push('/dashboard');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-bg-base flex relative overflow-hidden">
            <div className="fixed inset-0 bg-grid opacity-30 pointer-events-none" />
            <BackgroundNodes />

            {/* Left panel — branding */}
            <div className="hidden lg:flex flex-col justify-center px-16 w-[55%] relative">
                <div className="absolute inset-0 bg-radial-brand pointer-events-none" />
                <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.5 }}
                    className="relative z-10 max-w-lg"
                >
                    <div className="flex items-center gap-3 mb-10">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #00F5A0, #00D9FF)', boxShadow: '0 0 20px rgba(0,245,160,0.4)' }}>
                            <Zap className="w-5 h-5 text-bg-base" />
                        </div>
                        <div>
                            <p className="text-sm font-bold font-display text-text-1">CodeDebt Guardian</p>
                            <p className="text-[10px] text-text-3 font-mono uppercase tracking-widest">AI-Powered Platform</p>
                        </div>
                    </div>

                    <h1 className="text-5xl font-black font-display leading-tight mb-4">
                        <span className="text-text-1">Eliminate</span><br />
                        <span className="gradient-brand">Technical</span><br />
                        <span className="text-text-1">Debt.</span>
                    </h1>

                    <p className="text-text-2 text-base leading-relaxed mb-8 max-w-sm">
                        AI agents that detect, rank by business impact, and fix technical debt — automatically.
                    </p>

                    <div className="flex flex-wrap gap-2 mb-10">
                        <FeaturePill icon={Shield} label="Security scanning" />
                        <FeaturePill icon={Zap} label="AI auto-fix PRs" />
                        <FeaturePill icon={ArrowRight} label="Business impact ranking" />
                    </div>

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-4">
                        {[
                            { value: '10x', label: 'Faster debt resolution' },
                            { value: '146+', label: 'Issues detected' },
                            { value: '0.4s', label: 'Avg scan time' },
                        ].map((s) => (
                            <div key={s.label} className="glass-card rounded-xl p-3 text-center">
                                <p className="text-xl font-bold font-display gradient-brand">{s.value}</p>
                                <p className="text-[10px] text-text-3 mt-0.5">{s.label}</p>
                            </div>
                        ))}
                    </div>
                </motion.div>
            </div>

            {/* Right panel — login form */}
            <div className="flex-1 flex items-center justify-center px-6 py-12 relative">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 }}
                    className="w-full max-w-sm"
                >
                    {/* Mobile logo */}
                    <div className="flex items-center gap-2 mb-8 lg:hidden justify-center">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #00F5A0, #00D9FF)' }}>
                            <Zap className="w-4 h-4 text-bg-base" />
                        </div>
                        <span className="text-base font-bold font-display">CodeDebt Guardian</span>
                    </div>

                    <div className="glass-card rounded-2xl p-8">
                        <div className="mb-6">
                            <h2 className="text-xl font-bold font-display text-text-1">Welcome back</h2>
                            <p className="text-sm text-text-3 mt-1">Sign in to your account</p>
                        </div>

                        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                            <div>
                                <label className="block text-xs font-medium text-text-2 mb-1.5">Email</label>
                                <input
                                    {...register('email')}
                                    type="email"
                                    autoComplete="email"
                                    className="w-full h-11 px-4 rounded-xl bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20 transition-all"
                                    placeholder="you@company.com"
                                />
                                {errors.email && <p className="text-xs text-sev-critical mt-1">{errors.email.message}</p>}
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-text-2 mb-1.5">Password</label>
                                <div className="relative">
                                    <input
                                        {...register('password')}
                                        type={showPass ? 'text' : 'password'}
                                        autoComplete="current-password"
                                        className="w-full h-11 px-4 pr-10 rounded-xl bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20 transition-all"
                                        placeholder="••••••••"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPass(p => !p)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-text-3 hover:text-text-2 transition-colors"
                                    >
                                        {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                {errors.password && <p className="text-xs text-sev-critical mt-1">{errors.password.message}</p>}
                            </div>

                            <motion.button
                                whileHover={{ scale: 1.01 }}
                                whileTap={{ scale: 0.99 }}
                                type="submit"
                                disabled={loading}
                                className="w-full h-11 rounded-xl text-sm font-medium text-bg-base flex items-center justify-center gap-2 transition-all disabled:opacity-60 disabled:cursor-not-allowed mt-2"
                                style={{ background: 'linear-gradient(135deg, #00F5A0 0%, #00D9FF 100%)', boxShadow: '0 0 20px rgba(0,245,160,0.2)' }}
                            >
                                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                                {loading ? 'Signing in...' : 'Sign in'}
                            </motion.button>
                        </form>

                        <div className="mt-4 pt-4 border-t border-border">
                            <p className="text-xs text-text-3 text-center">
                                No account?{' '}
                                <Link href="/register" className="text-brand hover:text-brand-light transition-colors font-medium">
                                    Create one free
                                </Link>
                            </p>
                        </div>
                    </div>

                    <p className="text-[10px] text-text-3 text-center mt-4">
                        Protected by AI security · SOC 2 compliant
                    </p>
                </motion.div>
            </div>
        </div>
    );
}
