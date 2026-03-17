'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { FolderGit2, Plus, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useProjects } from '@/lib/hooks/useProjects';
import * as projectsApi from '@/lib/api/projects';
import { EmptyState } from '@/components/ui/EmptyState';
import { SkeletonTable } from '@/components/ui/SkeletonCard';
import { relativeTime } from '@/lib/utils/formatters';
import { useQueryClient } from '@tanstack/react-query';

export default function ProjectsPage() {
    const router = useRouter();
    const queryClient = useQueryClient();
    const { data, isLoading } = useProjects();
    const projects = data?.projects ?? [];
    const [showCreate, setShowCreate] = useState(false);
    const [name, setName] = useState('');
    const [repoUrl, setRepoUrl] = useState('');
    const [creating, setCreating] = useState(false);

    const handleCreate = async () => {
        if (!name || !repoUrl) return;
        setCreating(true);
        try {
            await projectsApi.createProject({ name, repo_url: repoUrl });
            toast.success('Project created');
            setShowCreate(false);
            setName('');
            setRepoUrl('');
            queryClient.invalidateQueries({ queryKey: ['projects'] });
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed');
        } finally {
            setCreating(false);
        }
    };

    const handleDelete = async (id: string) => {
        try {
            await projectsApi.deleteProject(id);
            toast.success('Project deleted');
            queryClient.invalidateQueries({ queryKey: ['projects'] });
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed');
        }
    };

    if (isLoading) return <SkeletonTable rows={5} />;

    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 max-w-[900px]">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-text-1">Projects</h1>
                <button
                    onClick={() => setShowCreate(true)}
                    className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors"
                >
                    <Plus className="w-3.5 h-3.5" /> New Project
                </button>
            </div>

            {/* Create form */}
            {showCreate && (
                <div className="bg-bg-card border border-border rounded-xl p-4 space-y-3">
                    <input
                        type="text" value={name} onChange={(e) => setName(e.target.value)}
                        placeholder="Project name" className="w-full h-8 px-3 rounded-lg bg-bg-input border border-border text-xs text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-1 focus:ring-brand/30"
                    />
                    <input
                        type="url" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)}
                        placeholder="https://github.com/owner/repo" className="w-full h-8 px-3 rounded-lg bg-bg-input border border-border text-xs text-text-1 font-mono placeholder:text-text-3 focus:outline-none focus:ring-1 focus:ring-brand/30"
                    />
                    <div className="flex gap-2">
                        <button onClick={handleCreate} disabled={creating}
                            className="h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors disabled:opacity-50 flex items-center gap-1">
                            {creating && <Loader2 className="w-3 h-3 animate-spin" />} Create
                        </button>
                        <button onClick={() => setShowCreate(false)} className="h-8 px-3 rounded-lg border border-border text-xs text-text-2 hover:text-text-1 transition-colors">
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {projects.length === 0 ? (
                <EmptyState icon={FolderGit2} title="No projects" description="Create a project or connect GitHub to get started"
                    action={{ label: 'Create Project', onClick: () => setShowCreate(true) }} />
            ) : (
                <div className="bg-bg-card border border-border rounded-xl divide-y divide-border">
                    {projects.map((p) => (
                        <div key={p.id} className="flex items-center gap-4 px-4 py-3 hover:bg-bg-card-2 transition-colors">
                            <FolderGit2 className="w-4 h-4 text-text-3 shrink-0" />
                            <div className="min-w-0 flex-1">
                                <p className="text-xs font-medium text-text-1">{p.name}</p>
                                <p className="text-[10px] text-text-code font-mono truncate">{p.repo_url?.replace('https://github.com/', '')}</p>
                            </div>
                            <span className="text-[10px] text-text-3">{p.scan_count ?? 0} scans</span>
                            <span className="text-[10px] text-text-3">{relativeTime(p.created_at)}</span>
                            <button onClick={() => handleDelete(p.id)} className="text-text-3 hover:text-sev-critical transition-colors" aria-label="Delete project">
                                <Trash2 className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </motion.div>
    );
}
