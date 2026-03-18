'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
    ArrowRight, ArrowLeft, GitBranch, Loader2, CheckCircle2,
    AlertCircle, FolderGit2, ChevronRight, Terminal, Zap,
    Shield, Cpu, GitPullRequest, Search
} from 'lucide-react';
import { toast } from 'sonner';
import * as scansApi from '@/lib/api/scans';
import { useScanWebSocket } from '@/lib/hooks/useScanWebSocket';
import { cn } from '@/lib/utils/cn';
import type { ScanSummary, WSProgressStage } from '@/types/api';

const STAGE_CONFIG: Record<WSProgressStage | 'queued', { icon: any; label: string; desc: string; color: string }> = {
    queued:    { icon: Loader2,        label: 'Queued',           desc: 'Waiting to start',      color: '#6B7280' },
    detection: { icon: Search,         label: 'Debt Detection',   desc: 'AI scanning codebase',  color: '#00D9FF' },
    ranking:   { icon: Zap,            label: 'Priority Ranking', desc: 'Business impact score', color: '#FFD60A' },
    fixing:    { icon: Terminal,       label: 'Fix Generation',   desc: 'Generating AI fixes',   color: '#8B5CF6' },
    autopilot: { icon: GitPullRequest, label: 'PR Creation',      desc: 'Opening pull requests', color: '#00F5A0' },
};

const STAGE_ORDER = ['queued', 'detection', 'ranking', 'fixing', 'autopilot'] as const;

/* ── Repo Card ───────────────────────────────────────────────────────── */
function RepoCard({ url, onClick }: { url: string; onClick?: () => void }) {
    const parts = url.replace('https://github.com/', '').split('/');
    const owner = parts[0] ?? '';
    const repo = parts[1] ?? '';
    return (
        <div
            onClick={onClick}
            className="flex items-center gap-3 p-3 rounded-xl border border-border hover:border-brand/30 bg-bg-card hover:bg-bg-card-hover transition-all cursor-pointer group"
        >
            <div className="w-8 h-8 rounded-lg bg-brand/10 flex items-center justify-center flex-shrink-0">
                <FolderGit2 className="w-4 h-4 text-brand" />
            </div>
            <div className="min-w-0">
                <p className="text-sm font-medium text-text-1 font-mono truncate">{owner}/<span className="text-brand">{repo}</span></p>
                <p className="text-[10px] text-text-3 truncate">{url}</p>
            </div>
            <ChevronRight className="w-4 h-4 text-text-3 opacity-0 group-hover:opacity-100 ml-auto flex-shrink-0 transition-opacity" />
        </div>
    );
}

/* ── Pipeline Stage ──────────────────────────────────────────────────── */
function PipelineStage({
    stageKey, currentStage, pct, isLast
}: {
    stageKey: string; currentStage: string; pct: number; isLast: boolean;
}) {
    const config = STAGE_CONFIG[stageKey as keyof typeof STAGE_CONFIG];
    const currentIdx = STAGE_ORDER.indexOf(currentStage as any);
    const thisIdx = STAGE_ORDER.indexOf(stageKey as any);
    const isDone = thisIdx < currentIdx;
    const isActive = stageKey === currentStage;
    const Icon = config.icon;

    return (
        <div className="flex items-stretch gap-3">
            <div className="flex flex-col items-center">
                <div
                    className={cn(
                        'w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-500',
                        isDone ? 'bg-brand/20' : isActive ? 'bg-transparent' : 'bg-bg-card-2'
                    )}
                    style={isActive ? {
                        background: `${config.color}15`,
                        border: `1px solid ${config.color}40`,
                        boxShadow: `0 0 16px ${config.color}30`
                    } : isDone ? { border: '1px solid rgba(0,245,160,0.3)' } : { border: '1px solid rgba(255,255,255,0.06)' }}
                >
                    {isDone ? (
                        <CheckCircle2 className="w-4 h-4 text-brand" />
                    ) : isActive ? (
                        <Icon className="w-4 h-4 animate-spin" style={{ color: config.color }} />
                    ) : (
                        <Icon className="w-4 h-4 text-text-3" />
                    )}
                </div>
                {!isLast && (
                    <div className="w-px flex-1 my-1.5" style={{ background: isDone ? 'rgba(0,245,160,0.3)' : 'rgba(255,255,255,0.06)' }} />
                )}
            </div>
            <div className={cn('pb-4', isLast && 'pb-0')}>
                <p className={cn('text-sm font-medium transition-colors', isActive ? 'text-text-1' : isDone ? 'text-text-2' : 'text-text-3')}>
                    {config.label}
                </p>
                <p className="text-[10px] text-text-3 mt-0.5">{config.desc}</p>
                {isActive && (
                    <div className="mt-2 h-1 w-32 bg-bg-card-2 rounded-full overflow-hidden">
                        <motion.div
                            className="h-full rounded-full"
                            style={{ background: config.color }}
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.5 }}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}

/* ── Terminal Log ────────────────────────────────────────────────────── */
function TerminalLog({ messages }: { messages: string[] }) {
    const ref = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
    }, [messages]);

    return (
        <div ref={ref} className="bg-bg-code border border-border rounded-xl p-3 h-28 overflow-y-auto scrollbar-thin font-mono">
            {messages.length === 0 ? (
                <p className="text-[10px] text-text-3 flex items-center gap-2">
                    <span className="text-brand animate-pulse">▊</span> Waiting for output...
                </p>
            ) : (
                messages.slice(-12).map((msg, i) => (
                    <p key={i} className="text-[10px] text-text-2 leading-relaxed">
                        <span className="text-brand/40 select-none">&gt; </span>{msg}
                    </p>
                ))
            )}
            <p className="text-[10px] text-text-3 flex items-center gap-1">
                <span className="text-brand blink">▊</span>
            </p>
        </div>
    );
}

/* ── Main Page ───────────────────────────────────────────────────────── */
export default function NewScanWizardPage() {
    const router = useRouter();
    const [step, setStep] = useState(0);
    const [repoUrl, setRepoUrl] = useState('');
    const [urlError, setUrlError] = useState('');
    const [branch, setBranch] = useState('main');
    const [scanId, setScanId] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [scanCompleted, setScanCompleted] = useState(false);

    const onComplete = useCallback((summary: ScanSummary) => {
        setScanCompleted(true);
        toast.success(`Scan complete — ${summary?.total_issues ?? 0} issues found`, {
            description: 'AI analysis finished successfully',
        });
    }, []);

    const { stage, pct, messages, error: wsError } = useScanWebSocket(scanId, onComplete);

    const validateUrl = (url: string): boolean => {
        if (!url.startsWith('https://github.com/')) {
            setUrlError('Must be a GitHub URL (https://github.com/...)');
            return false;
        }
        const parts = url.replace('https://github.com/', '').split('/').filter(Boolean);
        if (parts.length < 2) {
            setUrlError('Must include owner/repo (e.g. github.com/owner/repo)');
            return false;
        }
        setUrlError('');
        return true;
    };

    const handleStartScan = async () => {
        if (!validateUrl(repoUrl)) return;
        setSubmitting(true);
        try {
            const res = await scansApi.createScan({ repo_url: repoUrl, branch });
            setScanId(res.scan_id);
            setStep(2);
        } catch (err: any) {
            toast.error(err.message ?? 'Failed to start scan');
        } finally {
            setSubmitting(false);
        }
    };

    const RECENT = [
        'https://github.com/Priyanshjain10/Codedebt_Guardian',
    ];

    return (
        <div className="min-h-screen relative flex items-start justify-center py-8 px-4">
            <div className="fixed inset-0 bg-grid opacity-50 pointer-events-none" />
            <div className="fixed inset-0 bg-radial-brand pointer-events-none" />

            <div className="relative z-10 w-full max-w-xl">
                {/* Header */}
                <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 text-center">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-brand/20 bg-brand/5 mb-3">
                        <Shield className="w-3.5 h-3.5 text-brand" />
                        <span className="text-xs font-medium text-brand">AI Scan Wizard</span>
                    </div>
                    <h1 className="text-2xl font-bold font-display gradient-brand">Analyze Your Codebase</h1>
                    <p className="text-sm text-text-3 mt-1">AI-powered detection across all files in seconds</p>
                </motion.div>

                {/* Step indicators */}
                <div className="flex items-center justify-center gap-2 mb-6">
                    {['Select Repo', 'Configure', 'Running'].map((label, i) => (
                        <div key={label} className="flex items-center gap-2">
                            <div className={cn(
                                'flex items-center gap-1.5 px-3 py-1 rounded-full text-xs transition-all',
                                step === i ? 'bg-brand text-bg-base font-medium' :
                                step > i ? 'text-brand border border-brand/30' :
                                'text-text-3 border border-border'
                            )}>
                                {step > i ? <CheckCircle2 className="w-3 h-3" /> : <span className="w-4 text-center">{i + 1}</span>}
                                <span className="hidden sm:block">{label}</span>
                            </div>
                            {i < 2 && <div className={cn('w-6 h-px transition-colors', step > i ? 'bg-brand/40' : 'bg-border')} />}
                        </div>
                    ))}
                </div>

                {/* Card */}
                <AnimatePresence mode="wait">
                    {step === 0 && (
                        <motion.div
                            key="step-0"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.2 }}
                            className="glass-card rounded-2xl p-6 space-y-4"
                        >
                            <div>
                                <label className="text-xs font-medium text-text-2 block mb-2">GitHub Repository URL</label>
                                <div className="relative">
                                    <FolderGit2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-3" />
                                    <input
                                        value={repoUrl}
                                        onChange={(e) => { setRepoUrl(e.target.value); setUrlError(''); }}
                                        onKeyDown={(e) => e.key === 'Enter' && validateUrl(repoUrl) && setStep(1)}
                                        placeholder="https://github.com/owner/repo"
                                        className="w-full h-11 pl-10 pr-4 rounded-xl bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20 transition-all font-mono"
                                    />
                                </div>
                                {urlError && (
                                    <p className="text-xs text-sev-critical mt-1.5 flex items-center gap-1">
                                        <AlertCircle className="w-3 h-3" /> {urlError}
                                    </p>
                                )}
                            </div>

                            {RECENT.length > 0 && (
                                <div>
                                    <p className="text-[10px] font-medium text-text-3 uppercase tracking-wider mb-2">Recent</p>
                                    <div className="space-y-2">
                                        {RECENT.map(url => (
                                            <RepoCard key={url} url={url} onClick={() => { setRepoUrl(url); setUrlError(''); }} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            <motion.button
                                whileHover={{ scale: 1.01 }}
                                whileTap={{ scale: 0.99 }}
                                onClick={() => validateUrl(repoUrl) && setStep(1)}
                                disabled={!repoUrl}
                                className="w-full h-11 rounded-xl text-sm font-medium text-bg-base flex items-center justify-center gap-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                                style={{ background: 'linear-gradient(135deg, #00F5A0 0%, #00D9FF 100%)', boxShadow: repoUrl ? '0 0 20px rgba(0,245,160,0.25)' : 'none' }}
                            >
                                Continue <ArrowRight className="w-4 h-4" />
                            </motion.button>
                        </motion.div>
                    )}

                    {step === 1 && (
                        <motion.div
                            key="step-1"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.2 }}
                            className="glass-card rounded-2xl p-6 space-y-5"
                        >
                            <div>
                                <label className="text-xs font-medium text-text-2 block mb-2">Branch</label>
                                <div className="relative">
                                    <GitBranch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-3" />
                                    <input
                                        value={branch}
                                        onChange={(e) => setBranch(e.target.value)}
                                        placeholder="main"
                                        className="w-full h-11 pl-10 pr-4 rounded-xl bg-bg-input border border-border text-sm text-text-1 placeholder:text-text-3 focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20 transition-all font-mono"
                                    />
                                </div>
                            </div>

                            <div className="p-3 rounded-xl border border-border bg-bg-card space-y-2">
                                <div className="flex items-center gap-2">
                                    <FolderGit2 className="w-3.5 h-3.5 text-brand" />
                                    <span className="text-xs font-mono text-text-1 truncate">{repoUrl.replace('https://github.com/', '')}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <GitBranch className="w-3.5 h-3.5 text-text-3" />
                                    <span className="text-xs font-mono text-text-2">{branch}</span>
                                </div>
                            </div>

                            <div className="grid grid-cols-3 gap-2">
                                {[
                                    { icon: Shield, label: 'Security' },
                                    { icon: Cpu, label: 'AI Analysis' },
                                    { icon: GitPullRequest, label: 'Auto PRs' },
                                ].map((f) => (
                                    <div key={f.label} className="flex flex-col items-center gap-1.5 p-2.5 rounded-lg bg-bg-card border border-border">
                                        <f.icon className="w-3.5 h-3.5 text-brand" />
                                        <span className="text-[10px] text-text-3">{f.label}</span>
                                    </div>
                                ))}
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={() => setStep(0)}
                                    className="flex items-center gap-1.5 h-11 px-4 rounded-xl border border-border text-sm text-text-2 hover:text-text-1 hover:border-border-strong transition-all"
                                >
                                    <ArrowLeft className="w-4 h-4" /> Back
                                </button>
                                <motion.button
                                    whileHover={{ scale: 1.01 }}
                                    whileTap={{ scale: 0.99 }}
                                    onClick={handleStartScan}
                                    disabled={submitting}
                                    className="flex-1 h-11 rounded-xl text-sm font-medium text-bg-base flex items-center justify-center gap-2 disabled:opacity-50"
                                    style={{ background: 'linear-gradient(135deg, #00F5A0 0%, #00D9FF 100%)', boxShadow: '0 0 20px rgba(0,245,160,0.25)' }}
                                >
                                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                                    {submitting ? 'Starting...' : 'Launch Scan'}
                                </motion.button>
                            </div>
                        </motion.div>
                    )}

                    {step === 2 && (
                        <motion.div
                            key="step-2"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.2 }}
                            className="glass-card rounded-2xl p-6 space-y-5"
                        >
                            {wsError && (
                                <div className="flex items-center gap-2 p-3 rounded-xl bg-sev-critical-bg border border-sev-critical/20">
                                    <AlertCircle className="w-4 h-4 text-sev-critical flex-shrink-0" />
                                    <span className="text-xs text-sev-critical">{wsError}</span>
                                </div>
                            )}

                            {/* Pipeline */}
                            <div className="space-y-0">
                                {STAGE_ORDER.map((key, i) => (
                                    <PipelineStage
                                        key={key}
                                        stageKey={key}
                                        currentStage={stage}
                                        pct={pct}
                                        isLast={i === STAGE_ORDER.length - 1}
                                    />
                                ))}
                            </div>

                            {/* Terminal */}
                            <TerminalLog messages={messages} />

                            {/* Completion CTA */}
                            <AnimatePresence>
                                {scanCompleted && scanId && (
                                    <motion.div
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        className="p-4 rounded-xl border border-brand/30 bg-brand/5 text-center"
                                        style={{ boxShadow: '0 0 24px rgba(0,245,160,0.1)' }}
                                    >
                                        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-brand/10 mx-auto mb-2">
                                            <CheckCircle2 className="w-5 h-5 text-brand" />
                                        </div>
                                        <p className="text-sm font-medium text-text-1 mb-1">Analysis Complete</p>
                                        <p className="text-xs text-text-3 mb-3">AI has finished scanning your codebase</p>
                                        <motion.button
                                            whileHover={{ scale: 1.02 }}
                                            whileTap={{ scale: 0.98 }}
                                            onClick={() => router.push(`/scans/${scanId}/issues`)}
                                            className="w-full h-10 rounded-xl text-sm font-medium text-bg-base flex items-center justify-center gap-2"
                                            style={{ background: 'linear-gradient(135deg, #00F5A0 0%, #00D9FF 100%)', boxShadow: '0 0 20px rgba(0,245,160,0.3)' }}
                                        >
                                            View Results <ChevronRight className="w-4 h-4" />
                                        </motion.button>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}