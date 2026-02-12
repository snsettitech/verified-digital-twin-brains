'use client';

import { createBrowserClient } from '@supabase/auth-helpers-nextjs';

// Default values for development - Vercel deployments MUST set these in dashboard
const DEFAULT_SUPABASE_URL = 'https://jvtffdbuwyhmcynauety.supabase.co';
const DEFAULT_SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2dGZmZGJ1d3lobWN5bmF1ZXR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjYwMTY1MzksImV4cCI6MjA4MTU5MjUzOX0.tRpBHBhL2GM9s6sSncrVrNnmtwxrzED01SzwjKRb37E';

export function createClient() {
    // NOTE: Use explicit `process.env.NEXT_PUBLIC_*` accesses so Next can inline these at build time.
    // Dynamic access like `process.env[name]` will not work reliably in the browser bundle.
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL || DEFAULT_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || DEFAULT_SUPABASE_ANON_KEY;

    if (!url || !key) {
        console.error(
            'Supabase credentials not configured. Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.'
        );
    }

    return createBrowserClient(url || 'missing', key || 'missing');
}

// Singleton instance for use in components
let browserClient: ReturnType<typeof createBrowserClient> | null = null;

export function getSupabaseClient() {
    if (!browserClient) {
        browserClient = createClient();
    }
    return browserClient;
}
