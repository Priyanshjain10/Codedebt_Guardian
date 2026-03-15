'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Key, Plus, Trash2, Copy, Loader2, AlertTriangle } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as apiKeysApi from '@/lib/api/apiKeys';
import { EmptyState } from '@/components/ui/EmptyState';
import { relativeTime } from '@/lib/utils/formatters';

export default function APIKeysPage() {
    const queryClient = useQueryClient();
    const { data, isLoading } = useQuery({
        queryKey: ['api-keys'],
        queryFn: () => apiKeysApi.listAPIKeys(),
    });
    const keys = data?.api_keys ?? [];

    const [showCreate, setShowCreate] = useState(false);
    const [label, setLabel] = useState('');
    const [creating, setCreating] = useState(false);
    const [newKey, setNewKey] = useState<string | null>(null);

    const handleCreate = async () => {
        if (!label) return;
        setCreating(true);
        try {
            const result = await apiKeysApi.createAPIKey(label);
            setNewKey(result.key);
            setLabel('');
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to create key');
        } finally {
            setCreating(false);
        }
    };

    const handleRevoke = async (id: string) => {
        try {
            await apiKeysApi.revokeAPIKey(id);
            toast.success('Key revoked');
            queryClient.invalidateQueries({ queryKey: ['api-keys'] });
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed');
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        toast.success('Copied to clipboard');
    };

    return (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-4 max-w-[700px]">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-lg font-semibold text-text-1">API Keys</h1>
                    <p className="text-xs text-text-3">Keys are shown once at creation. Store them securely.</p>
                </div>
                <button onClick={() => { setShowCreate(true); setNewKey(null); }}
                    className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light transition-colors">
                    <Plus className="w-3.5 h-3.5" /> Create Key
                </button>
            </div>

            {/* New key display */}
            <AnimatePresence>
                {newKey && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
                        className="bg-brand/5 border border-brand/20 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <AlertTriangle className="w-4 h-4 text-accent-amber" />
                            <span className="text-xs font-medium text-accent-amber">This key will not be shown again</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 text-xs bg-bg-code border border-border rounded px-3 py-2 font-mono text-text-code break-all">
                                {newKey}
                            </code>
                            <button onClick={() => copyToClipboard(newKey)}
                                className="h-8 w-8 rounded-lg border border-border flex items-center justify-center text-text-3 hover:text-text-2 transition-colors shrink-0">
                                <Copy className="w-3.5 h-3.5" />
                            </button>
                        </div>
                        <button onClick={() => setNewKey(null)} className="text-xs text-brand mt-2 hover:text-brand-light transition-colors">Done</button>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Create form */}
            {showCreate && !newKey && (
                <div className="bg-bg-card border border-border rounded-xl p-4 flex items-center gap-3">
                    <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Key label (e.g. Production)"
                        className="flex-1 h-8 px-3 rounded-lg bg-bg-input border border-border text-xs text-text-1 placeholder:text-text-3 focus:outline-none focus:ring-1 focus:ring-brand/30" />
                    <button onClick={handleCreate} disabled={creating || !label}
                        className="h-8 px-3 rounded-lg bg-brand text-white text-xs font-medium hover:bg-brand-light disabled:opacity-50 flex items-center gap-1 transition-colors">
                        {creating && <Loader2 className="w-3 h-3 animate-spin" />} Create
                    </button>
                    <button onClick={() => setShowCreate(false)} className="h-8 px-3 rounded-lg border border-border text-xs text-text-2 hover:text-text-1 transition-colors">Cancel</button>
                </div>
            )}

            {/* Key list */}
            {keys.length === 0 ? (
                <EmptyState icon={Key} title="No API keys" description="Create an API key to access the CodeDebt Guardian API"
                    action={{ label: 'Create Key', onClick: () => setShowCreate(true) }} />
            ) : (
                <div className="bg-bg-card border border-border rounded-xl divide-y divide-border">
                    {keys.map((k) => (
                        <div key={k.id} className="flex items-center gap-4 px-4 py-3">
                            <Key className="w-4 h-4 text-text-3 shrink-0" />
                            <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-mono text-text-code">{k.prefix}...</span>
                                    <span className="text-xs text-text-2">{k.label}</span>
                                </div>
                                <p className="text-[10px] text-text-3 mt-0.5">
                                    Created {relativeTime(k.created_at)}
                                    {k.last_used_at && ` · Last used ${relativeTime(k.last_used_at)}`}
                                </p>
                            </div>
                            <button onClick={() => handleRevoke(k.id)} className="text-text-3 hover:text-sev-critical transition-colors" aria-label="Revoke key">
                                <Trash2 className="w-3.5 h-3.5" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </motion.div>
    );
}
