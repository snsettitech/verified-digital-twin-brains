'use client';

import { useState, useEffect } from 'react';

interface InterviewControlsProps {
    isConnected: boolean;
    isRecording: boolean;
    connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
    onStart: () => void;
    onStop: () => void;
    disabled?: boolean;
    error?: string | null;
}

/**
 * Interview control buttons with visual feedback for connection state.
 */


export function InterviewControls({
    isConnected,
    isRecording,
    connectionStatus,
    onStart,
    onStop,
    disabled = false,
    error = null,
}: InterviewControlsProps) {
    const [duration, setDuration] = useState(0);

    // Timer effect
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

    const isLoading = connectionStatus === 'connecting';

    return (
        <div className="flex flex-col items-center gap-4">
            {/* Status indicator */}
            <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${getStatusColor()} ${isRecording ? 'animate-pulse' : ''}`} />
                <span className="text-sm text-slate-400 capitalize">{connectionStatus}</span>
                {isRecording && (
                    <span className="text-sm text-slate-300 font-mono ml-2">
                        {formatDuration(duration)}
                    </span>
                )}
            </div>

            {/* Main button */}
            <button
                onClick={isRecording ? onStop : onStart}
                disabled={disabled || isLoading}
                className={`
          relative w-20 h-20 rounded-full flex items-center justify-center
          transition-all duration-300 transform hover:scale-105
          focus:outline-none focus:ring-4 focus:ring-opacity-50
          ${isRecording
                        ? 'bg-red-500 hover:bg-red-600 focus:ring-red-500'
                        : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 focus:ring-purple-500'
                    }
          ${(disabled || isLoading) ? 'opacity-50 cursor-not-allowed scale-100' : 'shadow-lg'}
        `}
                aria-label={isRecording ? 'Stop interview' : 'Start interview'}
            >
                {isLoading ? (
                    <LoadingSpinner />
                ) : isRecording ? (
                    <StopIcon />
                ) : (
                    <MicrophoneIcon />
                )}

                {/* Pulsing ring when recording */}
                {isRecording && (
                    <span className="absolute inset-0 rounded-full ring-4 ring-red-500 ring-opacity-30 animate-ping" />
                )}
            </button>

            {/* Label */}
            <span className="text-sm text-slate-400">
                {isLoading
                    ? 'Connecting...'
                    : isRecording
                        ? 'Click to stop'
                        : 'Click to start'
                }
            </span>

            {/* Error Message */}
            {error && (
                <div className="mt-2 p-3 bg-red-500/10 border border-red-500/30 rounded-xl max-w-xs text-center">
                    <p className="text-red-400 text-xs font-medium">{error}</p>
                </div>
            )}
        </div>
    );
}

function MicrophoneIcon() {
    return (
        <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
    );
}

function StopIcon() {
    return (
        <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="6" width="12" height="12" rx="2" />
        </svg>
    );
}

function LoadingSpinner() {
    return (
        <svg className="w-8 h-8 text-white animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
    );
}

export default InterviewControls;
