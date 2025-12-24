'use client';

import React from 'react';

interface PageTransitionProps {
    children: React.ReactNode;
    className?: string;
}

// Simple page transition wrapper using CSS animations
export function PageTransition({ children, className = '' }: PageTransitionProps) {
    return (
        <div className={`animate-pageEnter ${className}`}>
            {children}
        </div>
    );
}

// Loading overlay for page transitions
export function PageLoadingOverlay({ isLoading }: { isLoading: boolean }) {
    if (!isLoading) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0a0a0f]/90 backdrop-blur-sm animate-fadeIn">
            <div className="flex flex-col items-center gap-4">
                <div className="relative">
                    <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                    <div className="absolute inset-0 w-12 h-12 border-4 border-transparent border-b-purple-500 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
                </div>
                <p className="text-slate-400 text-sm">Loading...</p>
            </div>
        </div>
    );
}

// Suspense fallback for lazy loading
export function PageSkeleton() {
    return (
        <div className="p-6 space-y-6 animate-pulse">
            {/* Header skeleton */}
            <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-white/5 rounded-xl" />
                <div className="space-y-2">
                    <div className="h-5 w-40 bg-white/5 rounded" />
                    <div className="h-3 w-24 bg-white/5 rounded" />
                </div>
            </div>

            {/* Tabs skeleton */}
            <div className="flex gap-2 border-b border-white/10 pb-4">
                {[1, 2, 3, 4, 5].map(i => (
                    <div key={i} className="h-8 w-20 bg-white/5 rounded-lg" />
                ))}
            </div>

            {/* Content skeleton */}
            <div className="grid grid-cols-4 gap-4">
                {[1, 2, 3, 4].map(i => (
                    <div key={i} className="h-24 bg-white/5 rounded-xl" />
                ))}
            </div>

            <div className="space-y-3">
                <div className="h-4 bg-white/5 rounded w-full" />
                <div className="h-4 bg-white/5 rounded w-5/6" />
                <div className="h-4 bg-white/5 rounded w-4/6" />
            </div>
        </div>
    );
}

export default PageTransition;
