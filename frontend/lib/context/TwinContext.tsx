'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import type { AuthChangeEvent, Session } from '@supabase/supabase-js';

// ============================================================================
// Types
// ============================================================================

export interface Twin {
    id: string;
    name: string;
    owner_id: string;
    tenant_id: string;
    specialization_id: string;
    is_active: boolean;
    settings?: Record<string, unknown>;
    system_instructions?: string;
    created_at: string;
    updated_at: string;
}

export interface UserProfile {
    id: string;
    email: string;
    full_name?: string;
    avatar_url?: string;
    tenant_id?: string;
    onboarding_completed: boolean;
    created_at?: string;
}

interface TwinContextType {
    // User state
    user: UserProfile | null;
    isAuthenticated: boolean;
    isLoading: boolean;

    // Twin state
    twins: Twin[];
    activeTwin: Twin | null;

    // Actions
    setActiveTwin: (twinId: string) => void;
    refreshTwins: () => Promise<void>;
    syncUser: () => Promise<UserProfile | null>;
}

const TwinContext = createContext<TwinContextType | undefined>(undefined);

// ============================================================================
// Provider Component
// ============================================================================

export function TwinProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [twins, setTwins] = useState<Twin[]>([]);
    const [activeTwin, setActiveTwinState] = useState<Twin | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    const supabase = getSupabaseClient();
    const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    // Get auth token
    const getToken = useCallback(async (): Promise<string | null> => {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token || null;
    }, [supabase]);

    // Sync user with backend (creates user record if first login)
    const syncUser = useCallback(async (): Promise<UserProfile | null> => {
        try {
            const token = await getToken();
            if (!token) return null;

            const response = await fetch(`${API_URL}/auth/sync-user`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                console.error('Failed to sync user:', response.statusText);
                return null;
            }

            const data = await response.json();
            setUser(data.user);
            return data.user;
        } catch (error) {
            console.error('Error syncing user:', error);
            return null;
        }
    }, [API_URL, getToken]);

    // Fetch user's twins
    const refreshTwins = useCallback(async () => {
        try {
            const token = await getToken();
            if (!token) return;

            const response = await fetch(`${API_URL}/auth/my-twins`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                console.error('Failed to fetch twins:', response.statusText);
                return;
            }

            const data = await response.json();
            setTwins(data.twins || []);

            // Set active twin from localStorage or first twin
            const savedTwinId = localStorage.getItem('activeTwinId');
            const activeTwinFromList = data.twins?.find((t: Twin) => t.id === savedTwinId) || data.twins?.[0];

            if (activeTwinFromList) {
                setActiveTwinState(activeTwinFromList);
                localStorage.setItem('activeTwinId', activeTwinFromList.id);
            }
        } catch (error) {
            console.error('Error fetching twins:', error);
        }
    }, [API_URL, getToken]);

    // Set active twin
    const setActiveTwin = useCallback((twinId: string) => {
        const twin = twins.find(t => t.id === twinId);
        if (twin) {
            setActiveTwinState(twin);
            localStorage.setItem('activeTwinId', twinId);
        }
    }, [twins]);

    // Initialize on auth state change
    useEffect(() => {
        let mounted = true;

        const initialize = async () => {
            setIsLoading(true);

            const { data: { session } } = await supabase.auth.getSession();

            if (session && mounted) {
                // Sync user and fetch twins
                await syncUser();
                await refreshTwins();
            }

            if (mounted) {
                setIsLoading(false);
            }
        };

        initialize();

        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event: AuthChangeEvent, session: Session | null) => {
                if (event === 'SIGNED_IN' && session && mounted) {
                    setIsLoading(true);
                    await syncUser();
                    await refreshTwins();
                    setIsLoading(false);
                } else if (event === 'SIGNED_OUT' && mounted) {
                    setUser(null);
                    setTwins([]);
                    setActiveTwinState(null);
                    localStorage.removeItem('activeTwinId');
                }
            }
        );

        return () => {
            mounted = false;
            subscription.unsubscribe();
        };
    }, [supabase, syncUser, refreshTwins]);

    const value: TwinContextType = {
        user,
        isAuthenticated: !!user,
        isLoading,
        twins,
        activeTwin,
        setActiveTwin,
        refreshTwins,
        syncUser
    };

    return (
        <TwinContext.Provider value={value}>
            {children}
        </TwinContext.Provider>
    );
}

// ============================================================================
// Hook
// ============================================================================

export function useTwin(): TwinContextType {
    const context = useContext(TwinContext);
    if (context === undefined) {
        throw new Error('useTwin must be used within a TwinProvider');
    }
    return context;
}

// Convenience hooks
export function useActiveTwin(): Twin | null {
    const { activeTwin } = useTwin();
    return activeTwin;
}

export function useUser(): UserProfile | null {
    const { user } = useTwin();
    return user;
}
