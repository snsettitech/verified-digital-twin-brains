'use client';

import React from 'react';

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
    children: React.ReactNode;
    className?: string;
    hover?: boolean;
    /** @deprecated gradient prop removed — use solid surfaces per TOKENS.md */
    gradient?: boolean;
    /** @deprecated glass prop removed — use overlay-panel for blur over visuals */
    glass?: boolean;
};

export function Card({
    children,
    className = '',
    hover = false,
    // gradient and glass accepted but ignored — solid surfaces only
    gradient: _gradient,
    glass: _glass,
    ...props
}: CardProps) {
    const base = 'rounded-[14px] border border-white/10 bg-[#0F1C2E] transition-shadow duration-200';
    const hoverStyles = hover ? 'hover:shadow-[0_4px_12px_rgba(0,0,0,0.50),0_2px_4px_rgba(0,0,0,0.30)]' : '';

    return (
        <div className={`${base} ${hoverStyles} ${className}`} {...props}>
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
        <div className={`px-6 py-4 border-b border-white/10 ${className}`}>
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
        <div className={`px-6 py-4 border-t border-white/10 rounded-b-[14px] ${className}`}>
            {children}
        </div>
    );
}
