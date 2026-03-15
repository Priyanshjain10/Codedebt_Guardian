import type { Metadata } from 'next';
import { Inter, Roboto_Mono } from 'next/font/google';
import { Providers } from './providers';
import '@/globals.css';

const geistSans = Inter({ subsets: ['latin'], variable: '--font-geist' });
const geistMono = Roboto_Mono({ subsets: ['latin'], variable: '--font-geist-mono' });

export const metadata: Metadata = {
    title: 'CodeDebt Guardian — AI-Powered Technical Debt Management',
    description: 'Detect, prioritize, and fix technical debt with AI agents. Get real-time analysis, auto-generated pull requests, and executive reports.',
    keywords: ['technical debt', 'code quality', 'AI', 'developer tools', 'static analysis'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className="dark">
            <body
                className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased bg-bg-base text-text-1`}
            >
                <Providers>{children}</Providers>
            </body>
        </html>
    );
}
