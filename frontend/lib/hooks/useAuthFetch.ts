'use client';

import { useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

/**
 * Custom hook for making authenticated API requests.
 * Automatically adds the Supabase auth token to all requests.
 */
export function useAuthFetch() {
    const supabase = getSupabaseClient();

    /**
     * Get the current auth token
     */
    const getAuthToken = useCallback(async (): Promise<string | null> => {
        try {
            const { data: { session } } = await supabase.auth.getSession();
            return session?.access_token || null;
        } catch (error) {
            console.error('Failed to get auth token:', error);
            return null;
        }
    }, [supabase]);

    /**
     * Make an authenticated fetch request
     */
    const authFetch = useCallback(async (
        endpoint: string,
        options: RequestInit = {}
    ): Promise<Response> => {
        const token = await getAuthToken();

        const headers: Record<string, string> = {
            ...(options.headers as Record<string, string> || {}),
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // Add Content-Type for JSON requests if body is present and not FormData
        if (options.body && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

        return fetch(url, {
            ...options,
            headers,
        });
    }, [getAuthToken]);

    /**
     * GET request helper
     */
    const get = useCallback(async (endpoint: string): Promise<Response> => {
        return authFetch(endpoint, { method: 'GET' });
    }, [authFetch]);

    /**
     * POST request helper
     */
    const post = useCallback(async (
        endpoint: string,
        body?: any
    ): Promise<Response> => {
        const options: RequestInit = { method: 'POST' };

        if (body instanceof FormData) {
            options.body = body;
        } else if (body) {
            options.body = JSON.stringify(body);
        }

        return authFetch(endpoint, options);
    }, [authFetch]);

    /**
     * PUT request helper
     */
    const put = useCallback(async (
        endpoint: string,
        body?: any
    ): Promise<Response> => {
        return authFetch(endpoint, {
            method: 'PUT',
            body: body ? JSON.stringify(body) : undefined,
        });
    }, [authFetch]);

    /**
     * DELETE request helper
     */
    const del = useCallback(async (endpoint: string): Promise<Response> => {
        return authFetch(endpoint, { method: 'DELETE' });
    }, [authFetch]);

    /**
     * PATCH request helper
     */
    const patch = useCallback(async (
        endpoint: string,
        body?: any
    ): Promise<Response> => {
        return authFetch(endpoint, {
            method: 'PATCH',
            body: body ? JSON.stringify(body) : undefined,
        });
    }, [authFetch]);

    return {
        authFetch,
        get,
        post,
        put,
        del,
        patch,
        getAuthToken,
        API_BASE_URL,
    };
}

/**
 * Standalone function to get auth headers (for use outside React components)
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
    const supabase = getSupabaseClient();
    const { data: { session } } = await supabase.auth.getSession();

    if (session?.access_token) {
        return { 'Authorization': `Bearer ${session.access_token}` };
    }

    return {};
}

/**
 * Standalone authenticated fetch for use outside hooks
 */
export async function authFetchStandalone(
    endpoint: string,
    options: RequestInit = {}
): Promise<Response> {
    const authHeaders = await getAuthHeaders();
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

    const headers: Record<string, string> = {
        ...authHeaders,
        ...(options.headers as Record<string, string> || {}),
    };

    // Add Content-Type for JSON requests if body is present and not FormData
    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    return fetch(url, {
        ...options,
        headers,
    });
}

/**
 * Standalone function to get auth token (for use outside React hooks, e.g., streaming)
 */
export async function getAuthToken(): Promise<string | null> {
    const supabase = getSupabaseClient();
    try {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token || null;
    } catch (error) {
        console.error('Failed to get auth token:', error);
        return null;
    }
}

export { API_BASE_URL };
