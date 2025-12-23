'use client';

import React, { useState, useEffect } from 'react';
import InterviewInterface from '../../../components/Chat/InterviewInterface';
import BrainGraph from '../../../components/Brain/BrainGraph';

export default function RightBrainPage() {
    const [activeTwin, setActiveTwin] = useState('eeeed554-9180-4229-a9af-0f8dd2c69e9b');
    const [refreshGraphTrigger, setRefreshGraphTrigger] = useState(0);
    const [nodeCount, setNodeCount] = useState(0);
    const [sessionTime, setSessionTime] = useState(0);

    // Session timer
    useEffect(() => {
        const interval = setInterval(() => {
            setSessionTime(prev => prev + 1);
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const handleGraphUpdate = () => {
        setRefreshGraphTrigger(prev => prev + 1);
        setNodeCount(prev => prev + 1);
    };

    return (
        <div className="flex flex-col h-[calc(100vh-theme(spacing.20))] p-6 md:p-10 max-w-[1920px] mx-auto w-full bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
            {/* Premium Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center text-white shadow-2xl shadow-indigo-500/40 animate-pulse-glow">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
                        </div>
                        <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 border-4 border-white rounded-full animate-pulse"></div>
                    </div>
                    <div>
                        <h1 className="text-3xl font-black tracking-tight bg-gradient-to-r from-slate-900 via-indigo-900 to-purple-900 bg-clip-text text-transparent">Right Brain Training</h1>
                        <p className="text-slate-500 font-medium flex items-center gap-2">
                            <span className="w-2 h-2 bg-indigo-500 rounded-full"></span>
                            Cognitive Interview Session
                        </p>
                    </div>
                </div>

                {/* Session Stats */}
                <div className="flex items-center gap-4">
                    <div className="glass-card px-4 py-2 flex items-center gap-3">
                        <div className="text-center">
                            <div className="text-2xl font-black text-indigo-600">{nodeCount}</div>
                            <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Concepts</div>
                        </div>
                        <div className="w-px h-8 bg-slate-200"></div>
                        <div className="text-center">
                            <div className="text-2xl font-black text-purple-600 font-mono">{formatTime(sessionTime)}</div>
                            <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Session</div>
                        </div>
                    </div>
                    <div className="px-4 py-2 bg-gradient-to-r from-purple-50 to-pink-50 text-purple-700 text-xs font-bold rounded-xl border border-purple-100 uppercase tracking-widest flex items-center gap-2 shadow-lg shadow-purple-100/50">
                        <div className="relative">
                            <span className="w-2 h-2 bg-purple-500 rounded-full block"></span>
                            <span className="absolute inset-0 w-2 h-2 bg-purple-500 rounded-full animate-ping"></span>
                        </div>
                        Scribe Recording
                    </div>
                </div>
            </div>

            {/* Main Grid with Glass Divider */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0 relative">
                {/* Glass Divider */}
                <div className="hidden lg:block absolute left-1/2 top-4 bottom-4 w-px bg-gradient-to-b from-transparent via-slate-200 to-transparent transform -translate-x-1/2 z-10"></div>

                {/* Left Pane: Interview Chat */}
                <div className="flex flex-col h-full min-h-0">
                    <InterviewInterface
                        twinId={activeTwin}
                        onGraphUpdate={handleGraphUpdate}
                    />
                </div>

                {/* Right Pane: Live Graph Visualization */}
                <div className="bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-900 rounded-3xl border border-slate-700/50 shadow-2xl overflow-hidden flex flex-col h-full min-h-0 relative">
                    {/* Graph Header Overlay */}
                    <div className="absolute top-0 left-0 right-0 p-6 bg-gradient-to-b from-slate-900 to-transparent z-10">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-sm font-black text-white/80 uppercase tracking-widest">Mental Model</h3>
                                <p className="text-xs text-slate-400 mt-1">Live knowledge graph • Updates in real-time</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                <span className="text-xs text-green-400 font-bold">SYNCED</span>
                            </div>
                        </div>
                    </div>

                    <BrainGraph
                        twinId={activeTwin}
                        refreshTrigger={refreshGraphTrigger}
                    />

                    {/* Graph Legend Overlay */}
                    <div className="absolute bottom-4 left-4 right-4 p-4 bg-slate-800/80 backdrop-blur-xl rounded-2xl border border-slate-700/50">
                        <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-indigo-500"></div>
                                    <span className="text-slate-300">Concept</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-purple-500"></div>
                                    <span className="text-slate-300">Self</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                                    <span className="text-slate-300">Knowledge</span>
                                </div>
                            </div>
                            <div className="text-slate-400 font-mono">{nodeCount} nodes</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

