'use client';

import React, { useState } from 'react';
import ChatInterface from '@/components/Chat/ChatInterface';
import { useTwin } from '@/lib/context/TwinContext';

interface SimulatorViewProps {
    twinId?: string;
    onBack?: () => void;
    mode?: 'owner' | 'public' | 'training';
    trainingSessionId?: string | null;
    publicShareToken?: string | null;
}

/**
 * Simulator View Component
 * 
 * Reusable component for the Twin Simulator.
 */
export function SimulatorView({ twinId, onBack, mode = 'owner', trainingSessionId, publicShareToken }: SimulatorViewProps) {
    const { activeTwin, isLoading } = useTwin();
    const effectiveTwinId = twinId || activeTwin?.id;
    const contextKey = `${mode}:${trainingSessionId || 'none'}`;
    const [conversationIdsByContext, setConversationIdsByContext] = useState<Record<string, string | null>>({});
    const [resetCounter, setResetCounter] = useState(0);
    const currentConversationId = conversationIdsByContext[contextKey] || null;

    const startNewSession = () => {
        setConversationIdsByContext((prev) => ({ ...prev, [contextKey]: null }));
        setResetCounter((prev) => prev + 1);
    };

    // Show loading state while fetching twin
    if (isLoading && !effectiveTwinId) {
        return (
            <div className="flex flex-col h-full bg-[#f8fafc] text-slate-900 font-sans p-6 md:p-10 rounded-2xl">
                <div className="flex items-center justify-center flex-1">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-600"></div>
                    <span className="ml-3 text-slate-600">Loading your twin...</span>
                </div>
            </div>
        );
    }

    // Show message if no twin available
    if (!effectiveTwinId) {
        return (
            <div className="flex flex-col h-full bg-[#f8fafc] text-slate-900 font-sans p-6 md:p-10 rounded-2xl">
                <div className="flex items-center justify-center flex-1">
                    <div className="text-center">
                        <p className="text-lg text-slate-600 mb-2">No twin selected</p>
                        <p className="text-sm text-slate-500">Please select or create a twin to use the simulator.</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-[calc(100vh-200px)] bg-[#f8fafc] text-slate-900 font-sans rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-white">
                <div className="flex items-center gap-2">
                    {onBack && (
                        <button
                            onClick={onBack}
                            className="bg-white border text-xs font-bold px-3 py-2 rounded-lg hover:bg-slate-50 transition-colors shadow-sm text-slate-600"
                        >
                            Back
                        </button>
                    )}
                    <button
                        onClick={startNewSession}
                        className="bg-indigo-600 text-white text-xs font-bold px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
                    >
                        New Session
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-hidden">
                <ChatInterface
                    twinId={effectiveTwinId}
                    tenantId={activeTwin?.tenant_id}
                    conversationId={currentConversationId}
                    onConversationStarted={(id) =>
                        setConversationIdsByContext((prev) => ({ ...prev, [contextKey]: id }))
                    }
                    resetKey={resetCounter}
                    mode={mode}
                    trainingSessionId={trainingSessionId}
                    publicShareToken={publicShareToken}
                />
            </div>
        </div>
    );
}
