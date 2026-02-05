'use client';

import React, { useEffect, useState } from 'react';
import ChatInterface from '../../../components/Chat/ChatInterface';
import GraphContext from '../../../components/Chat/GraphContext';
import { useTwin } from '@/lib/context/TwinContext';

export default function SimulatorPage() {
    const { activeTwin: contextTwin, isLoading } = useTwin();
    const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);

    const startNewSession = () => {
        setCurrentConversationId(null);
    };

    // Show loading state while fetching twin
    if (isLoading) {
        return (
            <div className="flex flex-col h-[calc(100vh-theme(spacing.20))] bg-[#f8fafc] text-slate-900 font-sans p-6 md:p-10">
                <div className="flex items-center justify-center flex-1">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-600"></div>
                    <span className="ml-3 text-slate-600">Loading your twin...</span>
                </div>
            </div>
        );
    }

    // Show message if no twin available
    if (!contextTwin?.id) {
        return (
            <div className="flex flex-col h-[calc(100vh-theme(spacing.20))] bg-[#f8fafc] text-slate-900 font-sans p-6 md:p-10">
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
        <div className="flex flex-col h-[calc(100vh-theme(spacing.20))] bg-[#f8fafc] text-slate-900 font-sans p-6 md:p-10">
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-extrabold tracking-tight">Simulator</h1>
                    <p className="text-sm text-slate-500 font-medium">Test your Digital Twin&apos;s responses as a guest.</p>
                </div>
                <button
                    onClick={startNewSession}
                    className="bg-white border text-xs font-bold px-4 py-2 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
                >
                    New Session
                </button>
            </div>

            {/* Graph Context Panel - Shows what the twin knows */}
            <GraphContext twinId={contextTwin.id} />

            <div className="flex-1 shadow-2xl rounded-2xl overflow-hidden bg-white border border-slate-200">
                <ChatInterface
                    twinId={contextTwin.id}
                    conversationId={currentConversationId}
                    onConversationStarted={setCurrentConversationId}
                />
            </div>
        </div>
    );
}
