'use client';

import React, { useState } from 'react';
import ChatInterface from '@/components/Chat/ChatInterface';
import GraphContext from '@/components/Chat/GraphContext';
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

    const settings = (activeTwin?.id === effectiveTwinId && activeTwin?.settings && typeof activeTwin.settings === 'object')
        ? (activeTwin.settings as Record<string, any>)
        : null;
    const intentProfile = settings?.intent_profile || {};
    const publicIntro = (settings?.public_intro || '').toString().trim();
    const hasIntentSummary = !!(intentProfile?.use_case || intentProfile?.audience || intentProfile?.boundaries || publicIntro);

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
        <div className="flex flex-col h-[600px] bg-[#f8fafc] text-slate-900 font-sans p-6 rounded-2xl border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h2 className="text-xl font-extrabold tracking-tight text-slate-800">Simulator</h2>
                    <p className="text-sm text-slate-500 font-medium">
                        {mode === 'training'
                            ? 'Test responses in owner training context.'
                            : "Test your Digital Twin's responses as a guest."}
                    </p>
                </div>
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

            <div className="bg-white border border-slate-200 rounded-xl p-4 mb-4">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-slate-800">Intent Summary</h3>
                    <span className="text-[10px] uppercase tracking-wider text-slate-400">Owner-provided</span>
                </div>
                {hasIntentSummary ? (
                    <div className="grid gap-2 text-xs text-slate-700">
                        {intentProfile?.use_case && (
                            <div>
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Primary use case</div>
                                <div>{intentProfile.use_case}</div>
                            </div>
                        )}
                        {intentProfile?.audience && (
                            <div>
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Audience & outcomes</div>
                                <div>{intentProfile.audience}</div>
                            </div>
                        )}
                        {intentProfile?.boundaries && (
                            <div>
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Boundaries</div>
                                <div>{intentProfile.boundaries}</div>
                            </div>
                        )}
                        {publicIntro && (
                            <div>
                                <div className="text-[10px] uppercase tracking-wider text-slate-400">Public intro</div>
                                <div>{publicIntro}</div>
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="text-xs text-slate-500">
                        No intent profile saved yet. Set this in Training → Intent to steer responses.
                    </div>
                )}
            </div>

            {/* Graph Context Panel - Shows what the twin knows */}
            <GraphContext twinId={effectiveTwinId} />

            <div className="flex-1 shadow-inner rounded-xl overflow-hidden bg-white border border-slate-200 mt-4 relative">
                <ChatInterface
                    twinId={effectiveTwinId}
                    tenantId={activeTwin?.tenant_id} // Fallback to context if needed, though strictly ChatInterface might need it
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
