'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
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
    specialization: string;
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
    // RBAC role - used for privilege checks (admin views, etc.)
    role?: 'owner' | 'viewer' | string;  // owner = admin, viewer = standard user
}

interface TwinContextType {
    // User state
    user: UserProfile | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;  // NEW: Explicit error state

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
    const [error, setError] = useState<string | null>(null);

    // ========================================================================
    // StrictMode + Race Protection Refs
    // ========================================================================
    const initRef = useRef(false);           // Prevents duplicate initialization in StrictMode
    const requestIdRef = useRef(0);          // Race protection: ignore stale responses
    const mountedRef = useRef(true);         // Track mounted state

    const supabase = getSupabaseClient();
    const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    // ========================================================================
    // Stable localStorage helpers
    // ========================================================================
    const getPersistedTwinId = useCallback((): string | null => {
        try {
            return typeof window !== 'undefined' ? localStorage.getItem('activeTwinId') : null;
        } catch {
            return null; // localStorage unavailable (SSR, private browsing)
        }
    }, []);

    const persistTwinId = useCallback((twinId: string) => {
        try {
            if (typeof window !== 'undefined') {
                localStorage.setItem('activeTwinId', twinId);
                console.log('[TwinContext] Persisted activeTwinId:', twinId);
            }
        } catch {
            // localStorage unavailable
        }
    }, []);

    // Get auth token (with timeout and retry logic)
    const getToken = useCallback(async (): Promise<string | null> => {
        const maxRetries = 3;
        const baseTimeout = 5000;

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                console.log(`[TwinContext] getToken attempt ${attempt}/${maxRetries}`);
                const timeoutPromise = new Promise<null>((resolve) => {
                    setTimeout(() => resolve(null), baseTimeout * attempt);
                });

                const result = await Promise.race([
                    supabase.auth.getSession(),
                    timeoutPromise
                ]) as any;

                const token = result?.data?.session?.access_token || null;
                if (token) {
                    console.log('[TwinContext] Token obtained successfully');
                    return token;
                }

                console.warn(`[TwinContext] No token on attempt ${attempt}`);
            } catch (e) {
                console.warn(`[TwinContext] getToken attempt ${attempt} failed:`, e);
            }
        }

        console.error('[TwinContext] All token retrieval attempts failed');
        return null;
    }, [supabase]);

    // Sync user with backend
    const syncUser = useCallback(async (): Promise<UserProfile | null> => {
        try {
            const token = await getToken();
            if (!token) return null;

            const url = `${API_URL}/auth/sync-user`;
            console.log('[TwinContext] syncUser fetching:', url);
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            console.log('[TwinContext] syncUser response:', response.status, response.statusText);
            if (!response.ok) {
                console.error('[TwinContext] Failed to sync user:', response.status, response.statusText);
                return null;
            }

            const data = await response.json();
            if (mountedRef.current) {
                setUser(data.user);
            }
            return data.user;
        } catch (error) {
            console.error('[TwinContext] Error syncing user (network?):', error);
            return null;
        }
    }, [API_URL, getToken]);

    // ========================================================================
    // Stable Selection Algorithm
    // ========================================================================
    const selectActiveTwin = useCallback((
        twinsList: Twin[],
        currentActiveTwinId: string | null
    ): Twin | null => {
        if (twinsList.length === 0) {
            console.log('[TwinContext] selectActiveTwin: No twins available');
            return null;
        }

        const persistedId = getPersistedTwinId();

        // Priority 1: Current activeTwin state (if exists in new list)
        if (currentActiveTwinId) {
            const found = twinsList.find(t => t.id === currentActiveTwinId);
            if (found) {
                console.log('[TwinContext] selectActiveTwin: Keeping current state:', currentActiveTwinId);
                return found;
            }
        }

        // Priority 2: localStorage (if exists in new list)
        if (persistedId) {
            const found = twinsList.find(t => t.id === persistedId);
            if (found) {
                console.log('[TwinContext] selectActiveTwin: Using localStorage:', persistedId);
                return found;
            }
        }

        // Priority 3: Deterministic default (first in ordered list)
        const defaultTwin = twinsList[0];
        console.log('[TwinContext] selectActiveTwin: Using default (first):', defaultTwin.id);
        return defaultTwin;
    }, [getPersistedTwinId]);

    // ========================================================================
    // refreshTwins with Race Protection
    // ========================================================================
    const refreshTwins = useCallback(async () => {
        // Race protection: increment request ID
        const thisRequestId = ++requestIdRef.current;
        console.log('[TwinContext] refreshTwins called, requestId:', thisRequestId);
        setError(null);

        try {
            const token = await getToken();

            // Race check after async
            if (thisRequestId !== requestIdRef.current) {
                console.log('[TwinContext] refreshTwins: Stale request, ignoring');
                return;
            }

            if (!token) {
                console.error('[TwinContext] No auth token available');
                if (mountedRef.current) setError('Authentication required. Please sign in.');
                return;
            }

            const url = `${API_URL}/auth/my-twins`;
            console.log('[TwinContext] refreshTwins fetching:', url);
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            // Race check after fetch
            if (thisRequestId !== requestIdRef.current) {
                console.log('[TwinContext] refreshTwins: Stale after fetch, ignoring');
                return;
            }

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`[TwinContext] API error ${response.status}: ${errorText}`);
                if (mountedRef.current) setError(`Failed to fetch twins: ${response.status}`);
                return;
            }

            const data = await response.json();
            const twinsList: Twin[] = Array.isArray(data) ? data : (data.twins || []);
            console.log('[TwinContext] refreshTwins received:', twinsList.length, 'twins');

            // Final race check before state update
            if (thisRequestId !== requestIdRef.current || !mountedRef.current) {
                console.log('[TwinContext] refreshTwins: Stale before setState, ignoring');
                return;
            }

            setTwins(twinsList);

            // Use stable selection algorithm
            // CRITICAL: Pass current activeTwin.id from state to preserve selection
            setActiveTwinState(prevActiveTwin => {
                const selected = selectActiveTwin(twinsList, prevActiveTwin?.id || null);
                if (selected) {
                    persistTwinId(selected.id);
                }
                console.log('[TwinContext] refreshTwins complete. Active:', selected?.id, 'Total:', twinsList.length);
                return selected;
            });

        } catch (err) {
            if (thisRequestId === requestIdRef.current && mountedRef.current) {
                console.error('[TwinContext] Error fetching twins:', err);
                setError('Network error fetching twins');
            }
        }
    }, [API_URL, getToken, selectActiveTwin, persistTwinId]);

    // ========================================================================
    // Set active twin (user action)
    // ========================================================================
    const setActiveTwin = useCallback((twinId: string) => {
        const twin = twins.find(t => t.id === twinId);
        if (twin) {
            setActiveTwinState(twin);
            persistTwinId(twinId);
            console.log('[TwinContext] User selected twin:', twinId);
        } else {
            console.warn('[TwinContext] setActiveTwin: Twin not found in list:', twinId);
        }
    }, [twins, persistTwinId]);

    // ========================================================================
    // Initialization (StrictMode-safe)
    // ========================================================================
    useEffect(() => {
        mountedRef.current = true;

        const initialize = async () => {
            // StrictMode guard: prevent duplicate initialization
            if (initRef.current) {
                console.log('[TwinContext] Already initialized, skipping (StrictMode double-invoke)');
                return;
            }
            initRef.current = true;

            console.log('[TwinContext] Starting initialization...');
            console.log('[TwinContext] API_URL:', API_URL);
            setIsLoading(true);

            try {
                console.log('[TwinContext] Getting session...');
                const timeoutPromise = new Promise((_, reject) => {
                    setTimeout(() => reject(new Error('Session timeout')), 15000);
                });

                let session = null;
                try {
                    const result = await Promise.race([
                        supabase.auth.getSession(),
                        timeoutPromise
                    ]) as any;
                    session = result?.data?.session;
                    console.log('[TwinContext] Session:', session ? 'exists' : 'null');
                    if (session?.access_token) {
                        console.log('[TwinContext] Token present (redacted)');
                    }
                } catch (e) {
                    console.warn('[TwinContext] Session fetch failed:', e);
                }

                if (!mountedRef.current) return;

                if (session?.access_token) {
                    console.log('[TwinContext] Calling syncUser...');
                    await syncUser();
                    if (!mountedRef.current) return;

                    console.log('[TwinContext] Calling refreshTwins...');
                    await refreshTwins();
                } else {
                    console.log('[TwinContext] No session, user needs to sign in');
                    setError('Please sign in to continue');
                }
            } catch (error) {
                console.error('[TwinContext] Initialization error:', error);
            } finally {
                if (mountedRef.current) {
                    console.log('[TwinContext] Initialization complete');
                    setIsLoading(false);
                }
            }
        };

        initialize();

        // Auth state change listener
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event: AuthChangeEvent, session: Session | null) => {
                console.log('[TwinContext] Auth state change:', event);
                if (event === 'SIGNED_IN' && session && mountedRef.current) {
                    setIsLoading(true);
                    await syncUser();
                    await refreshTwins();
                    if (mountedRef.current) setIsLoading(false);
                } else if (event === 'SIGNED_OUT' && mountedRef.current) {
                    setUser(null);
                    setTwins([]);
                    setActiveTwinState(null);
                    try { localStorage.removeItem('activeTwinId'); } catch { }
                    initRef.current = false; // Reset for next sign-in
                }
            }
        );

        return () => {
            mountedRef.current = false;
            subscription.unsubscribe();
        };
    }, [supabase, syncUser, refreshTwins, API_URL]);

    const value: TwinContextType = {
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
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
