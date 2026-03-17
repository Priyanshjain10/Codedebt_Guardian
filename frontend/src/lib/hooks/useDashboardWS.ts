import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';

export function useDashboardWS(orgId: string | undefined | null) {
    const queryClient = useQueryClient();
    const wsRef = useRef<WebSocket | null>(null);
    const accessToken = useAuthStore((s) => s.accessToken);

    useEffect(() => {
        if (!orgId || !accessToken) return;

        let reconnectTimeout: ReturnType<typeof setTimeout>;
        let isConnecting = false;

        const connect = () => {
            if (isConnecting || wsRef.current?.readyState === WebSocket.OPEN) return;
            isConnecting = true;

            const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
            const ws = new WebSocket(`${wsUrl}/ws/dashboard/${orgId}?token=${accessToken}`);

            ws.onopen = () => {
                isConnecting = false;
                console.log('[Dashboard WS] Connected');
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'scan.completed' || data.type === 'scan.failed' || data.type === 'scan.queued') {
                        // Invalidate scan queries to refresh dashboard data
                        queryClient.invalidateQueries({ queryKey: ['scans'] });
                        // Also invalidate analytics to update charts if needed
                        queryClient.invalidateQueries({ queryKey: ['analytics'] });
                    }
                } catch (e) {
                    console.error('[Dashboard WS] Parse error:', e);
                }
            };

            ws.onclose = () => {
                isConnecting = false;
                wsRef.current = null;
                console.log('[Dashboard WS] Disconnected. Reconnecting in 3s...');
                reconnectTimeout = setTimeout(connect, 3000);
            };

            wsRef.current = ws;
        };

        connect();

        return () => {
            clearTimeout(reconnectTimeout);
            if (wsRef.current) {
                // Ensure we don't trigger auto-reconnect on unmount
                wsRef.current.onclose = null;
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [orgId, accessToken, queryClient]);
}
