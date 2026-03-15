import { create } from 'zustand';
import type { DebtSeverity, DebtCategory } from '@/types/api';

interface FilterState {
    severity: DebtSeverity[];
    category: DebtCategory[];
    issueStatus: 'unresolved' | 'all' | 'ignored';
    sortBy: 'score' | 'severity' | 'file' | 'effort';
    showQuickWins: boolean;
    searchQuery: string;
    setSeverity: (val: DebtSeverity[]) => void;
    setCategory: (val: DebtCategory[]) => void;
    setIssueStatus: (val: 'unresolved' | 'all' | 'ignored') => void;
    setSortBy: (val: 'score' | 'severity' | 'file' | 'effort') => void;
    setShowQuickWins: (val: boolean) => void;
    setSearchQuery: (val: string) => void;
    reset: () => void;
}

const DEFAULTS = {
    severity: [] as DebtSeverity[],
    category: [] as DebtCategory[],
    issueStatus: 'all' as const,
    sortBy: 'score' as const,
    showQuickWins: false,
    searchQuery: '',
};

export const useFilterStore = create<FilterState>()((set) => ({
    ...DEFAULTS,
    setSeverity: (severity) => set({ severity }),
    setCategory: (category) => set({ category }),
    setIssueStatus: (issueStatus) => set({ issueStatus }),
    setSortBy: (sortBy) => set({ sortBy }),
    setShowQuickWins: (showQuickWins) => set({ showQuickWins }),
    setSearchQuery: (searchQuery) => set({ searchQuery }),
    reset: () => set(DEFAULTS),
}));
