import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/types/api';

interface AuthState {
    user: User | null;
    accessToken: string | null;
    isAuthenticated: boolean;
    _hasHydrated: boolean;
    setHasHydrated: (state: boolean) => void;
    login: (token: string, user: User) => void;
    setUser: (user: User) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set) => ({
            user: null,
            accessToken: null,
            isAuthenticated: false,
            _hasHydrated: false,
            setHasHydrated: (state) => set({ _hasHydrated: state }),
            login: (token, user) =>
                set({ accessToken: token, user, isAuthenticated: true }),
            setUser: (user) => set({ user }),
            logout: () =>
                set({ accessToken: null, user: null, isAuthenticated: false }),
        }),
        {
            name: 'codedebt-auth',
            onRehydrateStorage: () => (state) => {
                state?.setHasHydrated(true);
            },
        },
    ),
);
