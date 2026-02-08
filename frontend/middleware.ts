import { NextResponse, type NextRequest } from 'next/server';
import { createServerClient, type CookieOptions } from '@supabase/auth-helpers-nextjs';

export async function middleware(request: NextRequest) {
    const response = NextResponse.next({
        request: {
            headers: request.headers,
        },
    });

    if (process.env.NODE_ENV !== 'production' && process.env.E2E_BYPASS_AUTH === '1') {
        return response;
    }

    const supabase = createServerClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
        {
            cookies: {
                get(name: string) {
                    return request.cookies.get(name)?.value;
                },
                set(name: string, value: string, options: CookieOptions) {
                    request.cookies.set({ name, value, ...options });
                    response.cookies.set({ name, value, ...options });
                },
                remove(name: string, options: CookieOptions) {
                    request.cookies.set({ name, value: '', ...options });
                    response.cookies.set({ name, value: '', ...options });
                },
            },
        }
    );

    // Refresh session if exists
    const { data: { session }, error: sessionError } = await supabase.auth.getSession();

    const isAuthPage = request.nextUrl.pathname.startsWith('/auth');
    const isCallbackPage = request.nextUrl.pathname === '/auth/callback';
    const isPublicPage = request.nextUrl.pathname === '/' ||
        request.nextUrl.pathname.startsWith('/share/');
    const isDashboard = request.nextUrl.pathname.startsWith('/dashboard');
    const isOnboarding = request.nextUrl.pathname.startsWith('/onboarding');

    // If user is not logged in and trying to access protected route
    if (!session && (isDashboard || isOnboarding)) {
        const redirectUrl = new URL('/auth/login', request.url);
        redirectUrl.searchParams.set('redirect', request.nextUrl.pathname);
        return NextResponse.redirect(redirectUrl);
    }

    // If user is logged in and trying to access auth pages (except callback and login)
    // Callback route must be allowed to complete the OAuth flow
    // Login page must be allowed even if user has session - errors may need to be displayed
    // (OAuth errors come as hash fragments which middleware can't detect, so we can't redirect based on them)
    // IMPORTANT: Don't redirect if there's an error in query params (from callback route)
    const hasErrorParam = request.nextUrl.searchParams.has('error');
    const isLoginPage = request.nextUrl.pathname === '/auth/login';
    if (session && isAuthPage && !isCallbackPage && !isLoginPage && !hasErrorParam) {
        // Only redirect to dashboard - don't follow redirect param to prevent loops
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    // If user is logged in and on landing page, redirect to dashboard
    if (session && request.nextUrl.pathname === '/') {
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    return response;
}

export const config = {
    matcher: [
        /*
         * Match all request paths except:
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         * - public folder
         */
        '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
    ],
};
