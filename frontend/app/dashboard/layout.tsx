'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { ToastProvider, SkipNavigation, SkipNavLink } from '@/components/ui';
import SyncStatusBanner from '@/components/ui/SyncStatusBanner';
import { ApiStatus } from '@/components/ui/ApiStatus';
import { ApiConnectivityBanner } from '@/components/ui/ApiConnectivityBanner';
import { EnvironmentBadge } from '@/components/ui/EnvironmentBadge';
import { DebugPanel } from '@/components/ui/DebugPanel';
import { TwinProvider } from '@/lib/context/TwinContext';
import { ProfileProvider } from '@/lib/context/ProfileContext';
import { ThemeProvider } from '@/lib/context/ThemeContext';

/**
 * Dashboard Layout
 * 
 * Provider hierarchy (simplified):
 * - TwinProvider: manages twin state (which twin is active)
 * - ToastProvider: notification system
 * - Sidebar: uses STATIC navigation config (no provider needed)
 * 
 * Navigation is infrastructure - it does NOT depend on:
 * - Twin selection
 * - API calls
 * - Feature flags
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ThemeProvider>
      <TwinProvider>
        <ProfileProvider>
          <ToastProvider>
          <SkipNavigation>
            <SkipNavLink href="#main-content">Skip to main content</SkipNavLink>
            <SkipNavLink href="#chat-input">Skip to chat</SkipNavLink>
          </SkipNavigation>
          <ApiConnectivityBanner />
          <EnvironmentBadge />
          <DebugPanel />
          <div className="flex h-screen bg-[#F8FAFC] dark:bg-slate-900 transition-colors">
            <Sidebar />
            <main id="main-content" role="main" className="flex-1 overflow-y-auto relative">
              <div className="max-w-6xl mx-auto p-4 md:p-8">
                <SyncStatusBanner />
                {children}
                <ApiStatus />
              </div>
            </main>
          </div>
          </ToastProvider>
        </ProfileProvider>
      </TwinProvider>
    </ThemeProvider>
  );
}
