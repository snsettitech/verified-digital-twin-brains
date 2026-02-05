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

    // Get auth token (with timeout to prevent hanging)
    const getToken = useCallback(async (): Promise<string | null> => {
        try {
            const timeoutPromise = new Promise<null>((resolve) => {
                setTimeout(() => resolve(null), 10000);
            });

            const result = await Promise.race([
                supabase.auth.getSession(),
                timeoutPromise
            ]) as any;

            return result?.data?.session?.access_token || null;
        } catch (e) {
            console.warn('[TwinContext] getToken failed:', e);
            return null;
        }
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
        console.log('[TwinContext] refreshTwins called');
        try {
            const token = await getToken();

            let data = null;

            if (token) {
                // Try authenticated endpoint
                console.log('[TwinContext] Trying authenticated /auth/my-twins');
                const response = await fetch(`${API_URL}/auth/my-twins`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (response.ok) {
                    data = await response.json();
                } else {
                    console.warn('Failed to fetch twins from auth endpoint:', response.statusText);
                }
            }

            // Fallback to public endpoint if auth failed or no token
            if (!data) {
                console.log('[TwinContext] Trying public /twins endpoint');
                const publicResponse = await fetch(`${API_URL}/twins`);
                if (publicResponse.ok) {
                    const publicData = await publicResponse.json();
                    data = { twins: publicData };
                }
            }

            if (data) {
                console.log('[TwinContext] Got twins:', data.twins?.length || 0);
                setTwins(data.twins || []);

                // Set active twin from localStorage or first twin
                const savedTwinId = localStorage.getItem('activeTwinId');
                const activeTwinFromList = data.twins?.find((t: Twin) => t.id === savedTwinId) || data.twins?.[0];

                if (activeTwinFromList) {
                    setActiveTwinState(activeTwinFromList);
                    localStorage.setItem('activeTwinId', activeTwinFromList.id);
                }
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
            console.log('[TwinContext] Starting initialization...');
            setIsLoading(true);

            try {
                // Try to get session with a timeout to prevent hanging
                console.log('[TwinContext] Getting session with timeout...');

                // Create a promise that rejects after 15 seconds
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('Session timeout')), 15000);
                });

                // Race the session fetch against the timeout
                let session = null;
                try {
                    const result = await Promise.race([
                        supabase.auth.getSession(),
                        timeoutPromise
                    ]) as any;
                    session = result?.data?.session;
                    console.log('[TwinContext] Session result:', session ? 'exists' : 'null');
                } catch (e) {
                    console.warn('[TwinContext] Session fetch timed out or failed, continuing without auth');
                }

                if (mounted) {
                    if (session) {
                        console.log('[TwinContext] Calling syncUser...');
                        await syncUser();
                        console.log('[TwinContext] syncUser done, calling refreshTwins...');
                    }
                    // Always try to fetch twins (even without session, some endpoints may be public)
                    await refreshTwins();
                    console.log('[TwinContext] refreshTwins complete');
                }
            } catch (error) {
                console.error('[TwinContext] Initialization error:', error);
            } finally {
                console.log('[TwinContext] Finally block, setting isLoading to false');
                if (mounted) {
                    setIsLoading(false);
                }
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
