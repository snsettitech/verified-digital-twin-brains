'use client';

import { useState, useEffect } from 'react';
import { useRealtimeInterview, TranscriptTurn } from '@/lib/hooks/useRealtimeInterview';
import { InterviewControls, TranscriptPanel } from '@/components/interview';

interface InterviewViewProps {
    onComplete?: () => void;
    onDataAvailable?: (data: any) => void;
}

/**
 * Interview View Component
 * 
 * Reusable component for real-time voice interview.
 */
export function InterviewView({ onComplete, onDataAvailable }: InterviewViewProps) {
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
    const [saving, setSaving] = useState(false);

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

    const handleStop = async () => {
        setSaving(true);
        const result = await stopInterview();
        setSaving(false);
        if (result && onDataAvailable) {
            onDataAvailable(result);
        }
        return result;
    };

    const handleFinish = async () => {
        if (isRecording) {
            await handleStop();
        }
        onComplete?.();
    };

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
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white">Interview Mode</h2>
                    <p className="text-sm text-slate-400">Tell me about yourself — your goals, preferences, and what matters to you.</p>
                </div>
                {/* Connection Status */}
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${getStatusColor()} animate-pulse`} />
                    <span className="text-slate-300 text-xs capitalize">
                        {connectionStatus}
                    </span>
                    {isRecording && (
                        <span className="text-slate-400 text-xs font-mono ml-2">
                            {formatDuration(duration)}
                        </span>
                    )}
                </div>
            </div>

            {/* Error Display */}
            {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 text-sm">{error}</p>
                </div>
            )}

            {/* Main Control */}
            <div className="bg-slate-800/50 backdrop-blur-md rounded-2xl p-6 border border-slate-700/50 shadow-xl">
                <InterviewControls
                    isConnected={isConnected}
                    isRecording={isRecording}
                    connectionStatus={connectionStatus}
                    onStart={startInterview}
                    onStop={handleStop}
                    error={error}
                />
                <p className="mt-4 text-xs text-slate-400 text-center">
                    Your interview is saved when you click Stop. Check Inbox after saving for proposed memories.
                </p>
                {!isRecording && transcript.length === 0 && (
                    <p className="mt-2 text-[11px] text-amber-300 text-center">
                        No transcript yet. Start the interview to capture memories.
                    </p>
                )}
            </div>

            {/* Transcript Panel */}
            <div className="min-h-[300px]">
                <TranscriptPanel
                    transcript={transcript}
                    isRecording={isRecording}
                    onClear={clearTranscript}
                />
            </div>

            {/* Instructions */}
            <div className="hidden md:block p-4 bg-slate-800/30 rounded-lg border border-slate-700/30">
                <h3 className="text-white font-medium mb-2 text-sm">Tips for a great interview</h3>
                <ul className="text-slate-400 text-xs space-y-1">
                    <li>• Speak naturally about what you&apos;re trying to accomplish</li>
                    <li>• Share your goals, both short and long-term</li>
                    <li>• Mention any constraints or limitations you face</li>
                    <li>• Express your preferences and how you like to work</li>
                    <li>• Let me know about any boundaries or topics to avoid</li>
                </ul>
            </div>

            {/* Footer Actions if needed */}
            {onComplete && (
                <div className="flex justify-end pt-4">
                    <button
                        onClick={handleFinish}
                        disabled={saving}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        {saving ? 'Saving...' : 'Finish Interview'}
                    </button>
                </div>
            )}
        </div>
    );
}
