'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import { ToastProvider } from '@/components/ui';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
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
  );
}
