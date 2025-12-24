'use client';

import React from 'react';

interface VerificationBadgeProps {
    status: 'unverified' | 'pending' | 'verified' | 'rejected';
    showText?: boolean;
}

export default function VerificationBadge({ status, showText = true }: VerificationBadgeProps) {
    if (status === 'unverified') return null;

    const config = {
        pending: {
            color: 'from-amber-400 to-orange-500',
            text: 'Verification Pending',
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
            )
        },
        verified: {
            color: 'from-blue-500 to-indigo-600',
            text: 'Verified Twin',
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                </svg>
            )
        },
        rejected: {
            color: 'from-red-500 to-rose-600',
            text: 'Verification Rejected',
            icon: (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
            )
        }
    };

    const current = config[status as keyof typeof config];
    if (!current) return null;

    return (
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-gradient-to-r ${current.color} text-white shadow-lg shadow-indigo-500/20`}>
            <div className="flex-shrink-0">
                {current.icon}
            </div>
            {showText && (
                <span className="text-[10px] font-black uppercase tracking-wider">
                    {current.text}
                </span>
            )}
        </div>
    );
}
