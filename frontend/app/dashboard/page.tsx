'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function DashboardPage() {
  const [systemStatus, setSystemStatus] = useState<'checking' | 'online' | 'offline' | 'degraded'>('checking');

  // Check system health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
          const data = await response.json();
          setSystemStatus(data.status === 'online' ? 'online' : 'degraded');
        } else {
          setSystemStatus('offline');
        }
      } catch (error) {
        setSystemStatus('offline');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-[#f8fafc] text-slate-900 font-sans">
      <main className="flex-1 max-w-7xl mx-auto w-full p-6 md:p-10 space-y-10">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Dashboard</h1>
          <div className="flex items-center gap-2 px-3 py-1 rounded-full border bg-white shadow-sm">
            <span className={`w-2 h-2 rounded-full ${systemStatus === 'online' ? 'bg-green-500' :
                systemStatus === 'degraded' ? 'bg-yellow-500' :
                  systemStatus === 'offline' ? 'bg-red-500' : 'bg-slate-300'
              }`}></span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              System: {systemStatus}
            </span>
          </div>
        </div>

        {/* Quick Actions Router */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

          {/* Left Brain */}
          <Link href="/dashboard/knowledge" className="group">
            <div className="bg-white p-8 rounded-[2rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300 h-full flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
              </div>
              <h3 className="text-xl font-black text-slate-800 mb-2">Left Brain</h3>
              <p className="text-sm text-slate-500 font-medium">Manage Sources & Facts</p>
            </div>
          </Link>

          {/* Right Brain */}
          <Link href="/dashboard/right-brain" className="group">
            <div className="bg-gradient-to-br from-indigo-600 to-purple-700 p-8 rounded-[2rem] text-white shadow-xl shadow-indigo-200 hover:shadow-2xl transition-all duration-300 h-full flex flex-col items-center text-center relative overflow-hidden">
              {/* Decorative bg */}
              <div className="absolute top-0 right-0 p-10 opacity-10">
                <svg className="w-32 h-32" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" /></svg>
              </div>

              <div className="w-16 h-16 bg-white/10 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>
              </div>
              <h3 className="text-xl font-black mb-2">Right Brain</h3>
              <p className="text-sm text-indigo-100 font-medium opacity-90">Start Cognitive Training</p>
              <div className="mt-8 px-4 py-2 bg-white/20 rounded-full text-xs font-bold uppercase tracking-widest animate-pulse">
                Recommended Next Step
              </div>
            </div>
          </Link>

          {/* Simulator */}
          <Link href="/dashboard/simulator" className="group">
            <div className="bg-white p-8 rounded-[2rem] border border-slate-200 shadow-sm hover:shadow-xl transition-all duration-300 h-full flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
              </div>
              <h3 className="text-xl font-black text-slate-800 mb-2">Simulator</h3>
              <p className="text-sm text-slate-500 font-medium">Test & Verify Output</p>
            </div>
          </Link>
        </div>

        <div className="p-6 bg-slate-100 rounded-2xl border border-slate-200 text-center text-slate-400 text-sm font-medium">
          Additional widgets and analytics coming soon to Dashboard Home.
        </div>

      </main>
    </div>
  );
}
