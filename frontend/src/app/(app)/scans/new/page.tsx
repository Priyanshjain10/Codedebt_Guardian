'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowRight, ArrowLeft, GitBranch, Loader2, CheckCircle2, AlertCircle, FolderGit2, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';
import * as scansApi from '@/lib/api/scans';
import { useScanWebSocket } from '@/lib/hooks/useScanWebSocket';
import { cn } from '@/lib/utils/cn';
import type { ScanSummary, WSProgressStage } from '@/types/api';

const STEPS = ['Select Repo', 'Configure', 'Running'] as const;

const STAGE_CONFIG: Record<WSProgressStage | 'queued', { icon: string; label: string }> = {
    queued: { icon: '⏳', label: 'Queued' },
    detection: { icon: '🔍', label: 'Debt Detection' },
    ranking: { icon: '📊', label: 'Priority Ranking' },
    fixing: { icon: '🔧', label: 'Fix Generation' },
    autopilot: { icon: '🔀', label: 'Autopilot' },
};

export default function NewScanWizardPage() {
    const router = useRouter();
    const [step, setStep] = useState(0);

    // Step 1 state
    const [repoUrl, setRepoUrl] = useState('');
    const [urlError, setUrlError] = useState('');

    // Step 2 state
    const [branch, setBranch] = useState('main');

    // Step 3 state
    const [scanId, setScanId] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [scanCompleted, setScanCompleted] = useState(false);

    /** Per user correction #3: WS only opens when scanId != null */
    const onComplete = useCallback(
        (summary: ScanSummary) => {
            setScanCompleted(true);
            toast.success(`Scan complete — ${summary?.total_issues ?? 0} issues found`);
        },
        [],
    );

    const { stage, pct, messages, error: wsError } = useScanWebSocket(scanId, onComplete);

    const validateUrl = (url: string): boolean => {
        if (!url.startsWith('https://github.com/')) {
            setUrlError('URL must start with https://github.com/');
            return false;
        }
        const parts = url.replace('https://github.com/', '').split('/').filter(Boolean);
        if (parts.length < 2) {
            setUrlError('URL must include owner/repo');
            return false;
        }
        setUrlError('');
        return true;
    };

    const handleStartScan = async () => {
        setSubmitting(true);
        try {
            const result = await scansApi.createScan({ repo_url: repoUrl, branch });
            setScanId(result.scan_id);
            setStep(2);
        } catch (err) {
            toast.error(err instanceof Error ? err.message : 'Failed to start scan');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-2xl mx-auto"
        >
            {/* Step indicator */}
            <div className="flex items-center gap-0 mb-8">
                {STEPS.map((s, i) => (
                    <div key={s} className="flex items-center flex-1">
                        <div className="flex items-center gap-2">
                            <div
                                className={cn(
                                    'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors',
                                    i < step
                                        ? 'bg-brand text-white'
                                        : i === step
                                            ? 'bg-brand/20 text-brand border border-brand'
                                            : 'bg-bg-card text-text-3 border border-border',
                                )}
                            >
                                {i < step ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
                            </div>
                            <span className={cn('text-xs', i === step ? 'text-text-1 font-medium' : 'text-text-3')}>
                                {s}
                            </span>
                        </div>
                        {i < STEPS.length - 1 && (
                            <div className={cn('flex-1 h-px mx-3', i < step ? 'bg-brand' : 'bg-border')} />
                        )}
                    </div>
                ))}
            </div>

            {/* Step content */}
            <AnimatePresence mode="wait">
                {step === 0 && (
                    <motion.div
                        key="step-0"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="bg-bg-card border border-border rounded-xl p-6 space-y-4"
                    >
                        <div className="flex items-center gap-2 mb-2">
                            <FolderGit2 className="w-5 h-5 text-brand" />
                            <h2 className="text-sm font-semibold text-text-1">Select Repository</h2>
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-text-2 mb-1.5">GitHub Repository URL</label>
                            <input
                                type="url"
                                value={repoUrl}
                                onChange={(e) => {
                                    setRepoUrl(e.target.value);
                                    if (urlError) validateUrl(e.target.value);
                                }}
                                placeholder="https://github.com/owner/repo"
                                className="w-full h-9 px-3 rounded-lg bg-bg-input border border-border text-sm text-text-1 font-mono placeholder:text-text-3 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand/50 transition-colors"
                            />
                            {urlError && <p className="text-xs text-sev-critical mt-1">{urlError}</p>}
                        </div>

                        <div className="flex justify-end">
                            <button
                                onClick={() => {
                                    if (validateUrl(repoUrl)) setStep(1);
                                }}
                                disabled={!repoUrl}
                                className="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors disabled:opacity-50"
                            >
                                Next <ArrowRight className="w-4 h-4" />
                            </button>
                        </div>
                    </motion.div>
                )}

                {step === 1 && (
                    <motion.div
                        key="step-1"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="bg-bg-card border border-border rounded-xl p-6 space-y-4"
                    >
                        <h2 className="text-sm font-semibold text-text-1">Configure Scan</h2>

                        <div>
                            <label className="block text-xs font-medium text-text-2 mb-1.5">Branch</label>
                            <div className="relative">
                                <GitBranch className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-3" />
                                <input
                                    type="text"
                                    value={branch}
                                    onChange={(e) => setBranch(e.target.value)}
                                    className="w-full h-9 pl-9 pr-3 rounded-lg bg-bg-input border border-border text-sm text-text-1 font-mono placeholder:text-text-3 focus:outline-none focus:ring-2 focus:ring-brand/30"
                                />
                            </div>
                        </div>

                        <div className="bg-bg-card-2 border border-border rounded-lg p-3">
                            <p className="text-xs text-text-1 font-mono truncate">{repoUrl}</p>
                            <p className="text-[10px] text-text-3 mt-1">Branch: {branch}</p>
                        </div>

                        <div className="flex justify-between">
                            <button
                                onClick={() => setStep(0)}
                                className="flex items-center gap-1.5 h-9 px-4 rounded-lg border border-border text-sm text-text-2 hover:text-text-1 transition-colors"
                            >
                                <ArrowLeft className="w-4 h-4" /> Back
                            </button>
                            <button
                                onClick={handleStartScan}
                                disabled={submitting}
                                className="flex items-center gap-1.5 h-9 px-4 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors disabled:opacity-50"
                            >
                                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                                Start Scan
                            </button>
                        </div>
                    </motion.div>
                )}

                {step === 2 && (
                    <motion.div
                        key="step-2"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="bg-bg-card border border-border rounded-xl p-6 space-y-4"
                    >
                        <h2 className="text-sm font-semibold text-text-1">Scan in Progress</h2>

                        {wsError && (
                            <div className="flex items-center gap-2 p-3 rounded-lg bg-sev-critical-bg border border-sev-critical/20">
                                <AlertCircle className="w-4 h-4 text-sev-critical" />
                                <span className="text-xs text-sev-critical">{wsError}</span>
                            </div>
                        )}

                        {/* Pipeline stages */}
                        <div className="space-y-3">
                            {(Object.entries(STAGE_CONFIG) as [WSProgressStage | 'queued', { icon: string; label: string }][]).map(([key, config]) => {
                                const stageOrder = ['queued', 'detection', 'ranking', 'fixing', 'autopilot'];
                                const currentIdx = stageOrder.indexOf(stage);
                                const thisIdx = stageOrder.indexOf(key);
                                const isDone = thisIdx < currentIdx;
                                const isActive = key === stage;

                                return (
                                    <div
                                        key={key}
                                        className={cn(
                                            'flex items-center gap-3 p-3 rounded-lg border transition-colors',
                                            isActive ? 'bg-brand-dim border-brand/30' : 'border-border',
                                            isDone && 'opacity-60',
                                        )}
                                    >
                                        <span className="text-lg">{config.icon}</span>
                                        <span className={cn('text-xs font-medium flex-1', isActive ? 'text-brand-light' : 'text-text-2')}>
                                            {config.label}
                                        </span>
                                        {isDone && <CheckCircle2 className="w-4 h-4 text-brand" />}
                                        {isActive && (
                                            <span className="text-xs font-mono text-brand">{pct}%</span>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        {/* Progress bar */}
                        <div className="h-1.5 rounded-full bg-bg-card-2 overflow-hidden">
                            <motion.div
                                className="h-full rounded-full bg-brand"
                                initial={{ width: 0 }}
                                animate={{ width: `${pct}%` }}
                                transition={{ duration: 0.3 }}
                            />
                        </div>

                        {/* Completion CTA */}
                        {scanCompleted && scanId && (
                            <motion.div
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="flex flex-col items-center gap-3 p-4 bg-brand/5 border border-brand/20 rounded-lg"
                            >
                                <CheckCircle2 className="w-8 h-8 text-brand" />
                                <p className="text-sm font-medium text-text-1">Scan Complete!</p>
                                <button
                                    onClick={() => router.push(`/scans/${scanId}/issues`)}
                                    className="w-full h-9 rounded-lg bg-brand text-white text-sm font-medium hover:bg-brand-light transition-colors flex items-center justify-center gap-2"
                                >
                                    View Results <ChevronRight className="w-4 h-4" />
                                </button>
                            </motion.div>
                        )}

                        {/* Log feed */}
                        {messages.length > 0 && (
                            <div className="bg-bg-code border border-border rounded-lg p-3 max-h-40 overflow-y-auto scrollbar-thin">
                                {messages.slice(-20).map((msg, i) => (
                                    <p key={i} className="text-[10px] font-mono text-text-2 leading-relaxed">
                                        {msg}
                                    </p>
                                ))}
                            </div>
                        )}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}
