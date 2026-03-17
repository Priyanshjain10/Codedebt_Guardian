/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
    theme: {
        extend: {
            colors: {
                bg: {
                    base: 'var(--bg-base)',
                    elevated: 'var(--bg-elevated)',
                    card: 'var(--bg-card)',
                    'card-2': 'var(--bg-card-2)',
                    input: 'var(--bg-input)',
                    code: 'var(--bg-code)',
                },
                border: {
                    subtle: 'var(--border-subtle)',
                    DEFAULT: 'var(--border-default)',
                    strong: 'var(--border-strong)',
                    focus: 'var(--border-focus)',
                },
                brand: {
                    DEFAULT: 'var(--brand)',
                    light: 'var(--brand-2)',
                    dim: 'var(--brand-dim)',
                },
                accent: {
                    cyan: 'var(--accent-cyan)',
                    violet: 'var(--accent-violet)',
                    amber: 'var(--accent-amber)',
                    rose: 'var(--accent-rose)',
                },
                sev: {
                    critical: 'var(--sev-critical)',
                    'critical-bg': 'var(--sev-critical-bg)',
                    high: 'var(--sev-high)',
                    'high-bg': 'var(--sev-high-bg)',
                    medium: 'var(--sev-medium)',
                    'medium-bg': 'var(--sev-medium-bg)',
                    low: 'var(--sev-low)',
                    'low-bg': 'var(--sev-low-bg)',
                },
                status: {
                    completed: 'var(--status-completed)',
                    running: 'var(--status-running)',
                    failed: 'var(--status-failed)',
                    queued: 'var(--status-queued)',
                    pending: 'var(--status-pending)',
                },
                text: {
                    1: 'var(--text-1)',
                    2: 'var(--text-2)',
                    3: 'var(--text-3)',
                    code: 'var(--text-code)',
                },
                chart: {
                    1: 'var(--chart-1)',
                    2: 'var(--chart-2)',
                    3: 'var(--chart-3)',
                    4: 'var(--chart-4)',
                    5: 'var(--chart-5)',
                },
            },
            fontFamily: {
                sans: ['var(--font-geist)', 'system-ui', 'sans-serif'],
                mono: ['var(--font-geist-mono)', 'JetBrains Mono', 'Fira Code', 'monospace'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
            },
        },
    },
    plugins: [],
};
