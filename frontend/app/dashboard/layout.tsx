'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { ToastProvider, SkipNavigation, SkipNavLink } from '@/components/ui';
import SyncStatusBanner from '@/components/ui/SyncStatusBanner';
import { TwinProvider } from '@/lib/context/TwinContext';

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
    <TwinProvider>
      <ToastProvider>
        <SkipNavigation>
          <SkipNavLink href="#main-content">Skip to main content</SkipNavLink>
          <SkipNavLink href="#chat-input">Skip to chat</SkipNavLink>
        </SkipNavigation>
        <div className="flex h-screen bg-[#F8FAFC]">
          <Sidebar />
          <main id="main-content" role="main" className="flex-1 overflow-y-auto relative">
            <div className="max-w-6xl mx-auto p-4 md:p-8">
              <SyncStatusBanner />
              {children}
            </div>
          </main>
        </div>
      </ToastProvider>
    </TwinProvider>
  );
}
