import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { createServerClient, type CookieOptions } from '@supabase/auth-helpers-nextjs';

import { resolveApiBaseUrl } from '@/lib/api';

function getServerSupabaseClient(cookieStore: Awaited<ReturnType<typeof cookies>>) {
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
        set(name: string, value: string, options: CookieOptions) {
          cookieStore.set({ name, value, ...options });
        },
        remove(name: string, options: CookieOptions) {
          cookieStore.set({ name, value: '', ...options });
        },
      },
    }
  );
}

export async function getAdminAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const supabase = getServerSupabaseClient(cookieStore);
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export async function adminBackendFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await getAdminAccessToken();
  if (!token) {
    return NextResponse.json({ detail: 'Authentication required' }, { status: 401 });
  }

  const headers = new Headers(init?.headers || {});
  headers.set('Authorization', `Bearer ${token}`);
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(`${resolveApiBaseUrl()}${path}`, {
    ...init,
    headers,
    cache: 'no-store',
  });
}

export async function proxyBackendJsonResponse(path: string, init?: RequestInit): Promise<Response> {
  const response = await adminBackendFetch(path, init);
  const text = await response.text();
  const contentType = response.headers.get('content-type') || 'application/json';
  return new Response(text, {
    status: response.status,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'no-store',
    },
  });
}
