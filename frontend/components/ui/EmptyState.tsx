'use client';

import React from 'react';
import Link from 'next/link';

interface EmptyStateProps {
    icon?: React.ReactNode;
    emoji?: string;
    title: string;
    description?: string;
    action?: {
        label: string;
        href?: string;
        onClick?: () => void;
    };
    secondaryAction?: {
        label: string;
        href?: string;
        onClick?: () => void;
    };
    variant?: 'default' | 'subtle' | 'card';
    className?: string;
}

export function EmptyState({
    icon,
    emoji,
    title,
    description,
    action,
    secondaryAction,
    variant = 'default',
    className = ''
}: EmptyStateProps) {
    const variantClasses = {
        default: '',
        subtle: 'py-8',
        card: 'bg-white/5 border border-white/10 rounded-2xl p-12'
    };

    const renderIcon = () => {
        if (emoji) {
            return (
                <div className="w-20 h-20 mx-auto mb-4 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-2xl flex items-center justify-center">
                    <span className="text-4xl">{emoji}</span>
                </div>
            );
        }
        if (icon) {
            return (
                <div className="w-20 h-20 mx-auto mb-4 bg-white/5 rounded-2xl flex items-center justify-center">
                    {icon}
                </div>
            );
        }
        return null;
    };

    const ActionButton = ({ action: a, primary = false }: { action: NonNullable<EmptyStateProps['action']>; primary?: boolean }) => {
        const buttonClasses = primary
            ? 'px-4 py-2 text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-lg shadow-lg shadow-indigo-500/20 transition-all'
            : 'px-4 py-2 text-sm font-medium text-slate-400 hover:text-white transition-colors';

        if (a.href) {
            return (
                <Link href={a.href} className={buttonClasses}>
                    {a.label}
                </Link>
            );
        }
        return (
            <button onClick={a.onClick} className={buttonClasses}>
                {a.label}
            </button>
        );
    };

    return (
        <div className={`text-center ${variantClasses[variant]} ${className}`}>
            {renderIcon()}

            <h3 className="text-lg font-semibold text-white mb-1">{title}</h3>

            {description && (
                <p className="text-slate-400 text-sm mb-6 max-w-sm mx-auto">{description}</p>
            )}

            {(action || secondaryAction) && (
                <div className="flex items-center justify-center gap-3">
                    {action && <ActionButton action={action} primary />}
                    {secondaryAction && <ActionButton action={secondaryAction} />}
                </div>
            )}
        </div>
    );
}

// Pre-configured empty states for common scenarios
export function EmptyKnowledge({ onAdd }: { onAdd?: () => void }) {
    return (
        <EmptyState
            emoji="📚"
            title="No knowledge sources yet"
            description="Add documents, URLs, or complete an interview to train your twin."
            action={{ label: "Add Your First Source", onClick: onAdd }}
            variant="card"
        />
    );
}

export function EmptyConversations({ twinId }: { twinId: string }) {
    return (
        <EmptyState
            emoji="💬"
            title="No conversations yet"
            description="Your twin is ready to chat. Start a conversation to see it in action."
            action={{ label: "Start Chatting", href: `/dashboard/twins/${twinId}?tab=chat` }}
            variant="subtle"
        />
    );
}

export function EmptyEscalations() {
    return (
        <EmptyState
            emoji="✅"
            title="All caught up!"
            description="No questions need review right now. Your twin is handling everything."
            variant="subtle"
        />
    );
}

export function EmptyActions({ onCreate }: { onCreate?: () => void }) {
    return (
        <EmptyState
            emoji="⚡"
            title="No automated actions"
            description="Create actions to automate workflows triggered by your twin's conversations."
            action={{ label: "Create Action", onClick: onCreate }}
            variant="card"
        />
    );
}

export function EmptyTwins() {
    return (
        <EmptyState
            emoji="🧠"
            title="No twins yet"
            description="Create your first digital twin to get started."
            action={{ label: "Create Your First Twin", href: "/onboarding" }}
            variant="card"
        />
    );
}

export function EmptySearch({ query }: { query: string }) {
    return (
        <EmptyState
            icon={
                <svg className="w-10 h-10 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
            }
            title={`No results for "${query}"`}
            description="Try adjusting your search or filter to find what you're looking for."
            variant="subtle"
        />
    );
}

export function ErrorState({
    title = "Something went wrong",
    description = "We encountered an error. Please try again.",
    onRetry
}: {
    title?: string;
    description?: string;
    onRetry?: () => void;
}) {
    return (
        <EmptyState
            icon={
                <svg className="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
            }
            title={title}
            description={description}
            action={onRetry ? { label: "Try Again", onClick: onRetry } : undefined}
            variant="subtle"
        />
    );
}

export default EmptyState;
