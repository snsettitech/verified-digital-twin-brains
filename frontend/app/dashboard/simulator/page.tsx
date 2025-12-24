'use client';

import React, { useState } from 'react';
import ChatInterface from '../../../components/Chat/ChatInterface';

export default function SimulatorPage() {
    const [activeTwin, setActiveTwin] = useState('eeeed554-9180-4229-a9af-0f8dd2c69e9b');
    const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);

    const startNewSession = () => {
        setCurrentConversationId(null);
    };

    return (
        <div className="flex flex-col h-[calc(100vh-theme(spacing.20))] bg-[#f8fafc] text-slate-900 font-sans p-6 md:p-10">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-extrabold tracking-tight">Simulator</h1>
                    <p className="text-sm text-slate-500 font-medium">Test your Digital Twin's responses as a guest.</p>
                </div>
                <button
                    onClick={startNewSession}
                    className="bg-white border text-xs font-bold px-4 py-2 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
                >
                    New Session
                </button>
            </div>

            <div className="flex-1 shadow-2xl rounded-2xl overflow-hidden bg-white border border-slate-200">
                <ChatInterface
                    twinId={activeTwin}
                    conversationId={currentConversationId}
                    onConversationStarted={setCurrentConversationId}
                />
            </div>
        </div>
    );
}
