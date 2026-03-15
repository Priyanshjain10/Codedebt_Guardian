'use client';

import { motion } from 'framer-motion';
import { Github, RefreshCw, ExternalLink, ScanSearch, Loader2 } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import * as githubApi from '@/lib/api/github';

export default function GitHubSettingsPage() {
    const queryClient = useQueryClient();
    const [syncing, setSyncing] = useState(false);

    const { data, isLoading } = useQuery({
        queryKey: ['github', 'repos'],
        queryFn: () => githubApi.listGitHubRepos(),
        staleTime: 5 * 60_000,
    });

    const repos = data?.repos ?? [];
    const isConnected = repos.length > 0;

    const handleSync = async () => {
        setSyncing(true);
        try {
            await githubApi.syncGitHubRepos();
            toast.success('Repos synced');
            queryClient.invalidateQueries({ queryKey: ['github', 'repos'] });
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Sync failed');
        } finally {
            setSyncing(false);
        }
    };

    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-6 max-w-[700px]">
            <h1 className="text-lg font-semibold text-text-1">GitHub Integration</h1>

            {!isConnected && !isLoading ? (
                <div className="bg-bg-card border border-border rounded-xl p-8 text-center">
                    <div className="w-14 h-14 rounded-2xl bg-bg-card-2 flex items-center justify-center mx-auto mb-4">
                        <Github className="w-7 h-7 text-text-2" />
                    </div>
                    <h2 className="text-sm font-semibold text-text-1 mb-1">Connect GitHub</h2>
                    <p className="text-xs text-text-3 mb-6 max-w-sm mx-auto">
                        Install the CodeDebt Guardian GitHub App to scan your repositories and create auto-fix pull requests.
                    </p>
                    <a
                        href={githubApi.getInstallUrl()}
                        className="inline-flex items-center gap-2 h-9 px-5 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors"
                    >
                        <Github className="w-4 h-4" />
                        Install GitHub App
                    </a>
                    <div className="grid grid-cols-3 gap-4 mt-8 text-xs text-text-3">
                        <div className="text-center"><span className="text-brand font-bold block mb-1">1</span>Install App</div>
                        <div className="text-center"><span className="text-brand font-bold block mb-1">2</span>Select Repos</div>
                        <div className="text-center"><span className="text-brand font-bold block mb-1">3</span>Start Scanning</div>
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-brand" />
                            <span className="text-xs font-medium text-text-1">GitHub Connected</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <button onClick={handleSync} disabled={syncing}
                                className="flex items-center gap-1.5 h-8 px-3 rounded-lg border border-border text-xs text-text-2 hover:text-text-1 transition-colors disabled:opacity-50">
                                {syncing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                Re-sync
                            </button>
                        </div>
                    </div>

                    <div className="bg-bg-card border border-border rounded-xl divide-y divide-border">
                        {repos.map((repo) => (
                            <div key={repo.id} className="flex items-center gap-4 px-4 py-3">
                                <Github className="w-4 h-4 text-text-3 shrink-0" />
                                <div className="min-w-0 flex-1">
                                    <p className="text-xs font-medium text-text-1">{repo.full_name}</p>
                                    <div className="flex items-center gap-2 mt-0.5">
                                        {repo.language && <span className="text-[10px] text-text-3">{repo.language}</span>}
                                        {repo.private && <span className="text-[10px] px-1 rounded bg-bg-card-2 text-text-3">Private</span>}
                                    </div>
                                </div>
                                <a href={repo.html_url} target="_blank" rel="noopener noreferrer" className="text-text-3 hover:text-text-2">
                                    <ExternalLink className="w-3.5 h-3.5" />
                                </a>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </motion.div>
    );
}
