'use client';

import React from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps {
    children: React.ReactNode;
    variant?: BadgeVariant;
    dot?: boolean;
    className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
    success: 'bg-gradient-to-r from-emerald-100 to-green-100 text-emerald-700 border-emerald-200',
    warning: 'bg-gradient-to-r from-amber-100 to-yellow-100 text-amber-700 border-amber-200',
    danger: 'bg-gradient-to-r from-red-100 to-rose-100 text-red-700 border-red-200',
    info: 'bg-gradient-to-r from-indigo-100 to-purple-100 text-indigo-700 border-indigo-200',
    neutral: 'bg-gradient-to-r from-slate-100 to-gray-100 text-slate-700 border-slate-200',
};

const dotStyles: Record<BadgeVariant, string> = {
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-red-500',
    info: 'bg-indigo-500',
    neutral: 'bg-slate-500',
};

export function Badge({ children, variant = 'neutral', dot = false, className = '' }: BadgeProps) {
    return (
        <span className={`
      inline-flex items-center gap-1.5 px-2.5 py-1 
      rounded-full text-xs font-semibold border
      ${variantStyles[variant]} ${className}
    `}>
            {dot && (
                <span className={`w-1.5 h-1.5 rounded-full ${dotStyles[variant]} animate-pulse`} />
            )}
            {children}
        </span>
    );
}
