'use client';

import { useRef, useEffect } from 'react';

interface TranscriptTurn {
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
}

interface TranscriptPanelProps {
    transcript: TranscriptTurn[];
    isRecording?: boolean;
    onClear?: () => void;
    className?: string;
}

/**
 * Live transcript display panel with auto-scroll and speaker labels.
 */
export function TranscriptPanel({
    transcript,
    isRecording = false,
    onClear,
    className = '',
}: TranscriptPanelProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new content arrives
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [transcript]);

    return (
        <div className={`bg-slate-800/50 rounded-xl border border-slate-700/50 overflow-hidden ${className}`}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
                <div className="flex items-center gap-2">
                    <h2 className="text-white font-medium">Transcript</h2>
                    {isRecording && (
                        <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full animate-pulse">
                            Live
                        </span>
                    )}
                </div>
                {transcript.length > 0 && onClear && (
                    <button
                        onClick={onClear}
                        className="text-slate-400 hover:text-white text-sm transition-colors"
                    >
                        Clear
                    </button>
                )}
            </div>

            {/* Content */}
            <div
                ref={scrollRef}
                className="p-4 min-h-[250px] max-h-[400px] overflow-y-auto scroll-smooth"
            >
                {transcript.length === 0 ? (
                    <EmptyState isRecording={isRecording} />
                ) : (
                    <div className="space-y-3">
                        {transcript.map((turn, index) => (
                            <TranscriptBubble key={`${turn.timestamp}-${index}`} turn={turn} />
                        ))}

                        {/* Typing indicator when recording */}
                        {isRecording && (
                            <div className="flex justify-center">
                                <TypingIndicator />
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function TranscriptBubble({ turn }: { turn: TranscriptTurn }) {
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
                {/* Speaker label */}
                <p className={`text-xs font-medium mb-1 ${isUser ? 'text-blue-200' : 'text-slate-400'}`}>
                    {isUser ? 'You' : 'Assistant'}
                </p>

                {/* Content */}
                <p className="text-sm leading-relaxed">{turn.content}</p>

                {/* Timestamp */}
                <p className={`text-xs mt-1 opacity-60 ${isUser ? 'text-blue-200' : 'text-slate-400'}`}>
                    {formatTime(turn.timestamp)}
                </p>
            </div>
        </div>
    );
}

function EmptyState({ isRecording }: { isRecording: boolean }) {
    return (
        <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-center">
            <svg className="w-12 h-12 text-slate-600 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-slate-500 text-sm">
                {isRecording
                    ? 'Listening... Start speaking.'
                    : 'Start the interview to see the transcript here.'}
            </p>
        </div>
    );
}

function TypingIndicator() {
    return (
        <div className="flex gap-1 px-4 py-2 bg-slate-700/50 rounded-full">
            <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
    );
}

function formatTime(timestamp: string): string {
    try {
        return new Date(timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return '';
    }
}

export default TranscriptPanel;
