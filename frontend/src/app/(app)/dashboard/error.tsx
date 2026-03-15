'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { AlertTriangle, Home, RefreshCw } from 'lucide-react';

export default function ErrorBoundary({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    useEffect(() => {
        // Log the error to an error reporting service
        console.error('Dashboard Error:', error);
    }, [error]);

    return (
        <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] p-6">
            <div className="bg-bg-card border border-border rounded-xl p-8 max-w-md w-full text-center space-y-6">
                <div className="w-12 h-12 rounded-full bg-sev-critical-bg flex items-center justify-center mx-auto">
                    <AlertTriangle className="w-6 h-6 text-sev-critical" />
                </div>
                <div className="space-y-2">
                    <h2 className="text-lg font-semibold text-text-1">Dashboard Error</h2>
                    <p className="text-sm text-text-2">{error.message || 'Something went wrong loading dashboard data.'}</p>
                </div>
                <div className="flex items-center justify-center gap-3">
                    <button
                        onClick={() => reset()}
                        className="flex items-center gap-2 h-9 px-4 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors"
                    >
                        <RefreshCw className="w-4 h-4" /> Try again
                    </button>
                    <Link
                        href="/dashboard"
                        className="flex items-center gap-2 h-9 px-4 rounded-lg border border-border text-sm text-text-2 hover:text-text-1 hover:bg-bg-card-2 transition-colors"
                    >
                        <Home className="w-4 h-4" /> Go back
                    </Link>
                </div>
            </div>
        </div>
    );
}
