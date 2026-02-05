'use client';

import { useState, useEffect } from 'react';
import { useRealtimeInterview, TranscriptTurn } from '@/lib/hooks/useRealtimeInterview';
import { InterviewControls, TranscriptPanel } from '@/components/interview';

/**
 * Interview Mode Page
 * 
 * Real-time voice interview for capturing user intent, goals, constraints,
 * preferences, and boundaries into the temporal knowledge graph.
 */
export default function InterviewPage() {
    const {
        isConnected,
        isRecording,
        error,
        transcript,
        connectionStatus,
        startInterview,
        stopInterview,
        clearTranscript,
    } = useRealtimeInterview({
        onTranscriptUpdate: (updated) => {
            console.log('Transcript updated:', updated.length, 'turns');
        },
        onError: (err) => {
            console.error('Interview error:', err);
        },
    });

    const [duration, setDuration] = useState(0);

    // Sync duration with recording state
    useEffect(() => {
        let interval: NodeJS.Timeout | null = null;
        if (isRecording) {
            interval = setInterval(() => {
                setDuration((d) => d + 1);
            }, 1000);
        } else {
            setDuration(0);
        }
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [isRecording]);

    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const getStatusColor = () => {
        switch (connectionStatus) {
            case 'connected':
                return 'bg-green-500';
            case 'connecting':
                return 'bg-yellow-500';
            case 'error':
                return 'bg-red-500';
            default:
                return 'bg-gray-400';
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
            <div className="max-w-4xl mx-auto px-4 py-8">
                {/* Header */}
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-white mb-2">
                        Interview Mode
                    </h1>
                    <p className="text-slate-400">
                        Tell me about yourself — your goals, preferences, and what matters to you.
                    </p>
                </div>

                {/* Connection Status */}
                <div className="flex items-center justify-center gap-2 mb-6">
                    <div className={`w-3 h-3 rounded-full ${getStatusColor()} animate-pulse`} />
                    <span className="text-slate-300 text-sm capitalize">
                        {connectionStatus}
                    </span>
                    {isRecording && (
                        <span className="text-slate-400 text-sm ml-4">
                            {formatDuration(duration)}
                        </span>
                    )}
                </div>

                {/* Error Display */}
                {error && (
                    <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                        <p className="text-red-400 text-sm">{error}</p>
                    </div>
                )}

                {/* Main Control */}
                <div className="bg-slate-800/50 backdrop-blur-md rounded-2xl p-8 border border-slate-700/50 shadow-xl mb-8">
                    <InterviewControls
                        isConnected={isConnected}
                        isRecording={isRecording}
                        connectionStatus={connectionStatus}
                        onStart={startInterview}
                        onStop={stopInterview}
                        error={error}
                    />
                </div>

                {/* Transcript Panel */}
                <TranscriptPanel
                    transcript={transcript}
                    isRecording={isRecording}
                    onClear={clearTranscript}
                />

                {/* Instructions */}
                <div className="mt-8 p-4 bg-slate-800/30 rounded-lg border border-slate-700/30">
                    <h3 className="text-white font-medium mb-2">Tips for a great interview</h3>
                    <ul className="text-slate-400 text-sm space-y-1">
                        <li>• Speak naturally about what you&apos;re trying to accomplish</li>
                        <li>• Share your goals, both short and long-term</li>
                        <li>• Mention any constraints or limitations you face</li>
                        <li>• Express your preferences and how you like to work</li>
                        <li>• Let me know about any boundaries or topics to avoid</li>
                    </ul>
                </div>
            </div>
        </div>
    );
}

function TranscriptItem({ turn }: { turn: TranscriptTurn }) {
    const isUser = turn.role === 'user';

    return (
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div
                className={`
          max-w-[80%] px-4 py-2 rounded-2xl
          ${isUser
                        ? 'bg-blue-600 text-white rounded-br-md'
                        : 'bg-slate-700 text-slate-100 rounded-bl-md'
                    }
        `}
            >
                <p className="text-sm">{turn.content}</p>
                <p className={`text-xs mt-1 ${isUser ? 'text-blue-200' : 'text-slate-400'}`}>
                    {new Date(turn.timestamp).toLocaleTimeString()}
                </p>
            </div>
        </div>
    );
}
