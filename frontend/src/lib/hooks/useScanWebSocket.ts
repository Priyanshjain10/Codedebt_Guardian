'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuthStore } from '@/store/authStore';
import type { ScanSummary, WSScanMessage, WSProgressStage } from '@/types/api';
import * as scansApi from '@/lib/api/scans';

/**
 * WebSocket hook for real-time scan progress.
 * Per user correction #3: opens WS only AFTER scanId is provided,
 * and polls GET /scans/{id} every 3s as fallback for the race condition
 * where the scan completes before the WS connection is established.
 */
export function useScanWebSocket(
    scanId: string | null,
    onComplete: (summary: ScanSummary) => void,
) {
    const { accessToken } = useAuthStore();
    const [stage, setStage] = useState<WSProgressStage | 'queued'>('queued');
    const [pct, setPct] = useState(0);
    const [messages, setMessages] = useState<string[]>([]);
    const [error, setError] = useState<string | null>(null);
    const completedRef = useRef(false);

    // Polling fallback — runs alongside WebSocket
    useEffect(() => {
        if (!scanId || completedRef.current) return;
        const interval = setInterval(async () => {
            try {
                const scan = await scansApi.getScan(scanId);
                if (scan.status === 'completed' && !completedRef.current) {
                    completedRef.current = true;
                    onComplete(scan.summary);
                }
                if (scan.status === 'failed' && !completedRef.current) {
                    completedRef.current = true;
                    setError('Scan failed');
                }
            } catch {
                // Polling errors are non-fatal
            }
        }, 3_000);
        return () => clearInterval(interval);
    }, [scanId, onComplete]);

    // WebSocket connection — only opens when scanId is available
    useEffect(() => {
        if (!scanId || !accessToken || completedRef.current) return;

        const wsBase = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
        const ws = new WebSocket(`${wsBase}/ws/scan/${scanId}?token=${accessToken}`);

        ws.onmessage = ({ data }) => {
            try {
                const raw = JSON.parse(data);
                // Normalize both old (scan.progress) and new (progress) message formats
                const msgType = raw.type;
                if (msgType === 'progress' || msgType === 'scan.progress') {
                    const stage = (raw.stage || raw.phase || 'detection') as WSProgressStage;
                    const pct = raw.pct ?? raw.percent ?? 0;
                    setStage(stage);
                    setPct(pct);
                    if (raw.message) setMessages((prev) => [...prev, raw.message]);
                } else if (msgType === 'completed' || msgType === 'scan.complete') {
                    if (!completedRef.current) {
                        completedRef.current = true;
                        const summary = raw.summary || raw.data?.summary || {};
                        onComplete(summary);
                    }
                } else if (msgType === 'error' || msgType === 'scan.error') {
                    setError(raw.message || 'Scan failed');
                }
                // heartbeat and connected are silently ignored
            } catch {
                // Ignore parse errors
            }
        };

        ws.onerror = () => {
            // WS errors are non-fatal — polling fallback keeps working
        };

        return () => {
            ws.close();
        };
    }, [scanId, accessToken, onComplete]);

    return { stage, pct, messages, error };
}
