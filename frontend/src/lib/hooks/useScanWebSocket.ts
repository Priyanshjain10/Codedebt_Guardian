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
                const msg: WSScanMessage = JSON.parse(data);
                switch (msg.type) {
                    case 'progress':
                        setStage(msg.stage);
                        setPct(msg.pct);
                        setMessages((prev) => [...prev, msg.message]);
                        break;
                    case 'completed':
                        if (!completedRef.current) {
                            completedRef.current = true;
                            onComplete(msg.summary);
                        }
                        break;
                    case 'error':
                        setError(msg.message);
                        break;
                    case 'heartbeat':
                    case 'connected':
                        break;
                }
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
