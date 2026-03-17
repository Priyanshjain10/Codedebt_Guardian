'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/authStore';
import { Sidebar } from '@/components/layout/Sidebar';
import { Topbar } from '@/components/layout/Topbar';
import { CommandPalette } from '@/components/layout/CommandPalette';

export default function AppLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const hasHydrated = useAuthStore((s) => s._hasHydrated);

    useEffect(() => {
        if (hasHydrated && !isAuthenticated) {
            router.replace('/login');
        }
    }, [hasHydrated, isAuthenticated, router]);

    if (!hasHydrated) return null;
    if (!isAuthenticated) return null;

    return (
        <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0">
                <Topbar />
                <main className="flex-1 overflow-y-auto scrollbar-thin p-6">
                    {children}
                </main>
            </div>
            <CommandPalette />
        </div>
    );
}
