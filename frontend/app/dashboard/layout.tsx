'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { ToastProvider } from '@/components/ui';
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
        <div className="flex h-screen bg-[#F8FAFC]">
          <Sidebar />
          <main className="flex-1 overflow-y-auto relative">
            <div className="max-w-6xl mx-auto p-8">
              {children}
            </div>
          </main>
        </div>
      </ToastProvider>
    </TwinProvider>
  );
}
