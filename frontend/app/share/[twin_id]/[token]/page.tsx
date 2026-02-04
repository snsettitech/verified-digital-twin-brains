'use client';

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { resolveApiBaseUrl } from '@/lib/api';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    citations?: string[];
    used_owner_memory?: boolean;
    owner_memory_topics?: string[];
    confidence_score?: number;
    isError?: boolean;
}

type RequestError = {
    type: 'network' | 'auth' | 'validation' | 'server' | 'unknown';
    message: string;
    canRetry: boolean;
};

function getErrorFromResponse(status: number, body?: string): RequestError {
    switch (status) {
        case 401:
        case 403:
            return { type: 'auth', message: 'This share link is invalid or has expired.', canRetry: false };
        case 422:
            return { type: 'validation', message: 'Your message couldn\'t be processed. Please try rephrasing.', canRetry: true };
        case 429:
            return { type: 'server', message: 'Too many requests. Please wait a moment and try again.', canRetry: true };
        case 500:
        case 502:
        case 503:
        case 504:
            return { type: 'server', message: 'Server error. Please try again in a moment.', canRetry: true };
        default:
            return { type: 'unknown', message: body || 'An unexpected error occurred.', canRetry: true };
    }
}

export default function PublicSharePage() {
    const params = useParams();
    const twinId = params?.twin_id as string;
    const shareToken = params?.token as string;

    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isValid, setIsValid] = useState<boolean | null>(null);
    const [twinName, setTwinName] = useState('AI Assistant');
    const [error, setError] = useState<string | null>(null);
    const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);
    const [requestError, setRequestError] = useState<RequestError | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const apiBaseUrl = useMemo(() => resolveApiBaseUrl(), []);

    // Storage key for persistence (scoped to share session)
    const storageKey = useMemo(() => {
        if (!twinId || !shareToken) return null;
        return `public_chat_${twinId}_${shareToken.slice(0, 8)}`;
    }, [twinId, shareToken]);

    // Persist messages to localStorage
    const persistMessages = useCallback((msgs: Message[]) => {
        if (!storageKey) return;
        try {
            localStorage.setItem(storageKey, JSON.stringify(msgs));
        } catch {
            // Ignore storage errors (private browsing, quota exceeded)
        }
    }, [storageKey]);

    // Load persisted messages on mount
    useEffect(() => {
        if (!storageKey) return;
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) {
                const parsed = JSON.parse(stored) as Message[];
                if (Array.isArray(parsed) && parsed.length > 0) {
                    // Filter out error messages from previous session
                    const cleanMessages = parsed.filter(m => !m.isError);
                    setMessages(cleanMessages);
                }
            }
        } catch {
            // Ignore parse errors
        }
    }, [storageKey]);

    // Persist on message changes
    useEffect(() => {
        if (messages.length > 0) {
            persistMessages(messages);
        }
    }, [messages, persistMessages]);

    useEffect(() => {
        validateShareToken();
    }, [twinId, shareToken]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const validateShareToken = async () => {
        try {
            const correlationId = Math.random().toString(36).substring(7);
            const response = await fetch(`${apiBaseUrl}/public/validate-share/${twinId}/${shareToken}`, {
                headers: { 'X-Correlation-Id': correlationId }
            });
            if (response.ok) {
                const data = await response.json();
                setIsValid(true);
                setTwinName(data.twin_name || 'AI Assistant');
            } else {
                setIsValid(false);
                setError('This share link is invalid or has expired.');
            }
        } catch (err) {
            setIsValid(false);
            setError('Unable to connect to the server. Please check your connection.');
        }
    };

    const sendMessage = async (overrideText?: string, options?: { retry?: boolean }) => {
        const text = (overrideText ?? input).trim();
        if (!text || isLoading || !isValid) return;

        // Clear any previous request error
        setRequestError(null);

        // Only add user message if not a retry
        if (!options?.retry) {
            const userMsg: Message = { role: 'user', content: text };
            setMessages(prev => [...prev, userMsg]);
            setInput('');
        }

        setLastUserMessage(text);
        setIsLoading(true);

        try {
            const correlationId = Math.random().toString(36).substring(7);
            const response = await fetch(`${apiBaseUrl}/public/chat/${twinId}/${shareToken}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Correlation-Id': correlationId
                },
                body: JSON.stringify({
                    message: text,
                    conversation_history: messages.filter(m => !m.isError).map(msg => ({
                        role: msg.role,
                        content: msg.content
                    }))
                })
            });

            if (response.ok) {
                const data = await response.json();
                if (data.status === 'queued') {
                    setMessages(prev => [...prev, {
                        role: 'assistant',
                        content: 'This question has been queued for the owner to review. Please check back shortly.',
                        isError: false
                    }]);
                } else {
                    setMessages(prev => [...prev, {
                        role: 'assistant',
                        content: data.response || 'No response',
                        citations: data.citations || [],
                        used_owner_memory: Boolean(data.used_owner_memory),
                        owner_memory_topics: Array.isArray(data.owner_memory_topics) ? data.owner_memory_topics : [],
                        confidence_score: data.confidence_score,
                        isError: false
                    }]);
                }
            } else {
                const errorText = await response.text().catch(() => '');
                const reqError = getErrorFromResponse(response.status, errorText);
                setRequestError(reqError);
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: reqError.message,
                    isError: true
                }]);
            }
        } catch (err) {
            const reqError: RequestError = {
                type: 'network',
                message: 'Unable to connect. Please check your internet connection.',
                canRetry: true
            };
            setRequestError(reqError);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: reqError.message,
                isError: true
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const retryLastMessage = () => {
        if (!lastUserMessage || isLoading) return;

        // Remove the last error message if present
        setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.isError) {
                return prev.slice(0, -1);
            }
            return prev;
        });

        setRequestError(null);
        sendMessage(lastUserMessage, { retry: true });
    };

    const clearHistory = () => {
        const confirmed = window.confirm('Clear this conversation?');
        if (!confirmed) return;
        setMessages([]);
        setLastUserMessage(null);
        setRequestError(null);
        if (storageKey) {
            try {
                localStorage.removeItem(storageKey);
            } catch {
                // Ignore
            }
        }
    };

    if (isValid === null) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-indigo-300 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-slate-300">Loading...</p>
                </div>
            </div>
        );
    }

    if (!isValid) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-4">
                <div className="max-w-md w-full bg-white/10 backdrop-blur-xl rounded-3xl p-8 text-center border border-white/10">
                    <div className="w-20 h-20 bg-red-500/20 rounded-2xl flex items-center justify-center mx-auto mb-6">
                        <svg className="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white mb-2">Link Not Found</h1>
                    <p className="text-slate-400">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex flex-col">
            {/* Header */}
            <header className="border-b border-white/10 backdrop-blur-xl bg-white/5">
                <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-xl flex items-center justify-center text-white shadow-lg">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        </div>
                        <div>
                            <h1 className="text-lg font-bold text-white">{twinName}</h1>
                            <p className="text-xs text-slate-400">Powered by VT-BRAIN</p>
                        </div>
                    </div>
                    {messages.length > 0 && (
                        <button
                            onClick={clearHistory}
                            className="text-xs text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/10"
                        >
                            Clear
                        </button>
                    )}
                </div>
            </header>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto px-4 py-6">
                <div className="max-w-4xl mx-auto space-y-4">
                    {messages.length === 0 && (
                        <div className="text-center py-20">
                            <div className="w-20 h-20 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-3xl flex items-center justify-center mx-auto mb-6 border border-indigo-500/30">
                                <svg className="w-10 h-10 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                                </svg>
                            </div>
                            <h2 className="text-2xl font-bold text-white mb-2">Start a Conversation</h2>
                            <p className="text-slate-400 max-w-md mx-auto">
                                Ask me anything! I'm here to help answer your questions.
                            </p>
                        </div>
                    )}

                    {messages.map((message, idx) => (
                        <div
                            key={idx}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[80%] px-4 py-3 rounded-2xl ${message.role === 'user'
                                    ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white'
                                    : message.isError
                                        ? 'bg-rose-500/10 backdrop-blur-sm text-rose-200 border border-rose-500/30'
                                        : 'bg-white/10 backdrop-blur-sm text-slate-200 border border-white/10'
                                    }`}
                            >
                                <p className="whitespace-pre-wrap">{message.content}</p>
                                {message.role === 'assistant' && !message.isError && (
                                    <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider">
                                        {message.used_owner_memory && (
                                            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                                </svg>
                                                Owner Memory
                                            </span>
                                        )}
                                        {message.used_owner_memory && message.owner_memory_topics && message.owner_memory_topics.length > 0 && (
                                            <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-200 border border-emerald-500/30">
                                                {message.owner_memory_topics.join(', ')}
                                            </span>
                                        )}
                                        {message.confidence_score !== undefined && (
                                            <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full border ${message.confidence_score > 0.8
                                                ? 'bg-green-500/20 text-green-300 border-green-500/30'
                                                : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                                                }`}>
                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                                {(message.confidence_score * 100).toFixed(0)}%
                                            </span>
                                        )}
                                        {message.citations?.map((_, i) => (
                                            <span key={i} className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/10 text-slate-300 border border-white/10">
                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                                                </svg>
                                                Source {i + 1}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {isLoading && (
                        <div className="flex justify-start">
                            <div className="bg-white/10 backdrop-blur-sm text-slate-200 border border-white/10 px-4 py-3 rounded-2xl">
                                <div className="flex items-center gap-3">
                                    <div className="flex gap-1">
                                        <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                                        <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                                        <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                                    </div>
                                    <span className="text-sm text-slate-400">Generating response…</span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Error Banner with Retry */}
            {requestError && requestError.canRetry && !isLoading && (
                <div className="border-t border-rose-500/30 bg-rose-500/10 backdrop-blur-xl">
                    <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3 text-rose-200">
                            <svg className="w-5 h-5 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <span className="text-sm">{requestError.message}</span>
                        </div>
                        <button
                            onClick={retryLastMessage}
                            className="shrink-0 px-4 py-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white text-sm font-medium rounded-lg transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            )}

            {/* Input Area */}
            <div className="border-t border-white/10 backdrop-blur-xl bg-white/5 p-4">
                <div className="max-w-4xl mx-auto">
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                            placeholder="Type your message..."
                            disabled={isLoading}
                            className="flex-1 px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-50"
                        />
                        <button
                            onClick={() => sendMessage()}
                            disabled={isLoading || !input.trim()}
                            className="px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-xl font-semibold hover:shadow-lg hover:shadow-indigo-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
