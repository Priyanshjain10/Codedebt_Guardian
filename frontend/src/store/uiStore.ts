import { create } from 'zustand';

interface UIState {
    sidebarCollapsed: boolean;
    commandPaletteOpen: boolean;
    toggleSidebar: () => void;
    setCommandPalette: (open: boolean) => void;
}

export const useUIStore = create<UIState>()((set) => ({
    sidebarCollapsed: false,
    commandPaletteOpen: false,
    toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    setCommandPalette: (open) => set({ commandPaletteOpen: open }),
}));
