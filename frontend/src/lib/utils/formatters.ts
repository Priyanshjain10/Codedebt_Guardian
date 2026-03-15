import { formatDistanceToNow, format, parseISO } from 'date-fns';

export function relativeTime(dateStr: string): string {
    try {
        return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
    } catch {
        return dateStr;
    }
}

export function formatDate(dateStr: string): string {
    try {
        return format(parseISO(dateStr), 'MMM d, yyyy');
    } catch {
        return dateStr;
    }
}

export function formatDateTime(dateStr: string): string {
    try {
        return format(parseISO(dateStr), 'MMM d, yyyy HH:mm');
    } catch {
        return dateStr;
    }
}

export function formatDuration(seconds: number | null): string {
    if (seconds === null || seconds === undefined) return '—';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
}

export function formatNumber(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toLocaleString();
}

export function formatScore(score: number): string {
    return score.toFixed(1);
}

export function truncateMiddle(str: string, maxLen: number): string {
    if (str.length <= maxLen) return str;
    const half = Math.floor((maxLen - 3) / 2);
    return `${str.slice(0, half)}...${str.slice(-half)}`;
}
