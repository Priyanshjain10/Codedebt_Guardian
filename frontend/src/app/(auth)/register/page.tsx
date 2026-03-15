'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { motion } from 'framer-motion';
import { Zap, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import * as authApi from '@/lib/api/auth';
import { useAuthStore } from '@/store/authStore';

const schema = z.object({
    name: z.string().min(2, 'Name required'),
    email: z.string().email('Valid email required'),
    password: z.string().min(6, 'At least 6 characters'),
});

type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
    const router = useRouter();
    const login = useAuthStore((s) => s.login);
    const [loading, setLoading] = useState(false);

    const { register, handleSubmit, formState: { errors } } = useForm<FormData>({ resolver: zodResolver(schema) });

    const onSubmit = async (data: FormData) => {
        setLoading(true);
        try {
            const tokens = await authApi.register(data);
            const user = await authApi.getMe(tokens.access_token);
            login(tokens.access_token, user);
            router.push('/dashboard');
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Registration failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-bg-base p-4">
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }} className="w-full max-w-sm">
                <div className="flex items-center gap-2 mb-8 justify-center">
                    <div className="w-8 h-8 rounded-lg bg-brand/20 flex items-center justify-center">
                        <Zap className="w-5 h-5 text-brand" />
                    </div>
                    <span className="text-lg font-semibold text-text-1">CodeDebt Guardian</span>
                </div>
                <div className="bg-bg-card border border-border rounded-xl p-6">
                    <h1 className="text-xl font-semibold text-text-1 mb-1">Create your account</h1>
                    <p className="text-sm text-text-2 mb-6">Start analyzing your codebase in seconds</p>
                    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                        <div>
                            <label className="block text-xs font-medium text-text-2 mb-1.5">Name</label>
                            <input {...register('name')} type="text" autoComplete="name" className="w-full h-9 px-3 rounded-lg bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand/50 transition-colors" placeholder="Jane Smith" />
                            {errors.name && <p className="text-xs text-sev-critical mt-1">{errors.name.message}</p>}
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-text-2 mb-1.5">Email</label>
                            <input {...register('email')} type="email" autoComplete="email" className="w-full h-9 px-3 rounded-lg bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand/50 transition-colors" placeholder="you@company.com" />
                            {errors.email && <p className="text-xs text-sev-critical mt-1">{errors.email.message}</p>}
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-text-2 mb-1.5">Password</label>
                            <input {...register('password')} type="password" autoComplete="new-password" className="w-full h-9 px-3 rounded-lg bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand/50 transition-colors" placeholder="••••••••" />
                            {errors.password && <p className="text-xs text-sev-critical mt-1">{errors.password.message}</p>}
                        </div>
                        <button type="submit" disabled={loading} className="w-full h-9 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
                            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                            Create account
                        </button>
                    </form>
                    <p className="text-xs text-text-3 text-center mt-4">
                        Already have an account?{' '}
                        <Link href="/login" className="text-brand hover:text-brand-light transition-colors">Sign in</Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
}
