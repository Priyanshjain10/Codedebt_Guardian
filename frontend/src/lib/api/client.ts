/* ── Base API Client ──────────────────────────────────────────────────── */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class APIError extends Error {
    constructor(public override message: string, public status: number, public detail?: unknown) {
        super(message);
        this.name = 'APIError';
    }
}

function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    try {
        const raw = localStorage.getItem('codedebt-auth');
        if (!raw) return null;
        const store = JSON.parse(raw);
        return store?.state?.accessToken ?? null;
    } catch {
        return null;
    }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = getToken();
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> ?? {}),
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (res.status === 401) {
        // Auto-logout on auth failure
        if (typeof window !== 'undefined') {
            localStorage.removeItem('codedebt-auth');
            window.location.href = '/login';
        }
        throw new APIError('Unauthorized', 401);
    }

    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new APIError(
            body.detail || body.message || `Request failed (${res.status})`,
            res.status,
            body,
        );
    }

    if (res.status === 204) return {} as T;
    return res.json();
}

export { API_BASE };
