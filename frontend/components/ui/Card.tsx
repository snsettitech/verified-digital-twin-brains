'use client';

import React from 'react';

interface CardProps {
    children: React.ReactNode;
    className?: string;
    hover?: boolean;
    gradient?: boolean;
    glass?: boolean;
}

export function Card({ children, className = '', hover = false, gradient = false, glass = false }: CardProps) {
    const baseStyles = 'rounded-2xl transition-all duration-200';
    const hoverStyles = hover ? 'hover:shadow-xl hover:-translate-y-1' : '';
    const gradientStyles = gradient
        ? 'bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 text-white'
        : 'bg-white border border-slate-200';
    const glassStyles = glass
        ? 'bg-white/70 backdrop-blur-xl border border-white/20 shadow-lg'
        : '';

    return (
        <div className={`${baseStyles} ${glass ? glassStyles : gradientStyles} ${hoverStyles} ${className}`}>
            {children}
        </div>
    );
}

interface CardHeaderProps {
    children: React.ReactNode;
    className?: string;
}

export function CardHeader({ children, className = '' }: CardHeaderProps) {
    return (
        <div className={`px-6 py-4 border-b border-slate-100 ${className}`}>
            {children}
        </div>
    );
}

interface CardContentProps {
    children: React.ReactNode;
    className?: string;
}

export function CardContent({ children, className = '' }: CardContentProps) {
    return (
        <div className={`px-6 py-4 ${className}`}>
            {children}
        </div>
    );
}

interface CardFooterProps {
    children: React.ReactNode;
    className?: string;
}

export function CardFooter({ children, className = '' }: CardFooterProps) {
    return (
        <div className={`px-6 py-4 border-t border-slate-100 bg-slate-50/50 rounded-b-2xl ${className}`}>
            {children}
        </div>
    );
}
