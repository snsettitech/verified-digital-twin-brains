import { createServerClient, type CookieOptions } from '@supabase/auth-helpers-nextjs';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export async function GET(request: NextRequest) {
    const requestUrl = new URL(request.url);
    const code = requestUrl.searchParams.get('code');
    const error = requestUrl.searchParams.get('error');
    const errorDescription = requestUrl.searchParams.get('error_description');
    const redirectParam = requestUrl.searchParams.get('redirect') || '/dashboard';

    // Handle OAuth errors
    if (error) {
        console.error('OAuth error:', error, errorDescription);
        const loginUrl = new URL('/auth/login', requestUrl.origin);
        loginUrl.searchParams.set('error', error);
        if (errorDescription) {
            loginUrl.searchParams.set('error_description', errorDescription);
        }
        if (redirectParam && redirectParam !== '/dashboard') {
            loginUrl.searchParams.set('redirect', redirectParam);
        }
        return NextResponse.redirect(loginUrl);
    }

    if (!code) {
        // No code parameter - redirect to login
        const loginUrl = new URL('/auth/login', requestUrl.origin);
        if (redirectParam && redirectParam !== '/dashboard') {
            loginUrl.searchParams.set('redirect', redirectParam);
        }
        return NextResponse.redirect(loginUrl);
    }

    try {
        const cookieStore = await cookies();

        const supabase = createServerClient(
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

        const { data: sessionData, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);

        if (exchangeError) {
            console.error('Session exchange error:', exchangeError);
            const loginUrl = new URL('/auth/login', requestUrl.origin);
            loginUrl.searchParams.set('error', 'session_exchange_failed');
            if (redirectParam && redirectParam !== '/dashboard') {
                loginUrl.searchParams.set('redirect', redirectParam);
            }
            return NextResponse.redirect(loginUrl);
        }

        // INTELLIGENT ROUTING: Call sync-user to determine if new or existing user
        // This also ensures the user record and tenant are created
        let finalRedirect = '/dashboard'; // Default for existing users

        if (sessionData?.session?.access_token) {
            try {
                const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
                const syncResponse = await fetch(`${backendUrl}/auth/sync-user`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${sessionData.session.access_token}`,
                        'Content-Type': 'application/json',
                    },
                });

                if (syncResponse.ok) {
                    const syncData = await syncResponse.json();
                    console.log('[Callback] Sync response:', syncData.status, 'needs_onboarding:', syncData.needs_onboarding);

                    // Route based on user status:
                    // - New users (status='created') -> onboarding
                    // - Existing users without twins (needs_onboarding=true) -> onboarding
                    // - Existing users with twins -> dashboard
                    if (syncData.status === 'created' || syncData.needs_onboarding) {
                        finalRedirect = '/onboarding';
                    } else {
                        finalRedirect = '/dashboard';
                    }
                } else {
                    console.error('[Callback] Sync-user failed:', syncResponse.status);
                    // Fall back to dashboard on error
                    finalRedirect = '/dashboard';
                }
            } catch (syncError) {
                console.error('[Callback] Error calling sync-user:', syncError);
                // Fall back to dashboard on error
                finalRedirect = '/dashboard';
            }
        }

        return NextResponse.redirect(new URL(finalRedirect, requestUrl.origin));
    } catch (error) {
        console.error('Callback error:', error);
        const loginUrl = new URL('/auth/login', requestUrl.origin);
        loginUrl.searchParams.set('error', 'callback_error');
        if (redirectParam && redirectParam !== '/dashboard') {
            loginUrl.searchParams.set('redirect', redirectParam);
        }
        return NextResponse.redirect(loginUrl);
    }
}
