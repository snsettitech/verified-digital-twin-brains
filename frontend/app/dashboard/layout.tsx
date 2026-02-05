'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import MobileNav from '@/components/MobileNav';
import { ToastProvider, SkipNavigation, SkipNavLink } from '@/components/ui';
import SyncStatusBanner from '@/components/ui/SyncStatusBanner';
import { TwinProvider } from '@/lib/context/TwinContext';
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
        <ToastProvider>
          <SkipNavigation>
            <SkipNavLink href="#main-content">Skip to main content</SkipNavLink>
            <SkipNavLink href="#chat-input">Skip to chat</SkipNavLink>
          </SkipNavigation>
          <div className="flex h-screen bg-[#F8FAFC] dark:bg-slate-900 transition-colors">
            {/* Mobile Navigation - visible on small screens */}
            <MobileNav />
            {/* Desktop Sidebar - hidden on mobile */}
            <div className="hidden md:block">
              <Sidebar />
            </div>
            <main id="main-content" role="main" className="flex-1 overflow-y-auto relative pt-16 md:pt-0">
              <div className="max-w-6xl mx-auto p-4 md:p-8">
                <SyncStatusBanner />
                {children}
              </div>
            </main>
          </div>
        </ToastProvider>
      </TwinProvider>
    </ThemeProvider>
  );
}
