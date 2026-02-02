'use client';

import React, { useState, useRef, useEffect } from 'react';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

interface ChatTabProps {
    twinId: string;
    twinName: string;
    onSendMessage?: (message: string) => Promise<string>;
}

interface DebugContext {
    text: string;
    score: number;
    source_id?: string;
    source_filename?: string;
    is_verified: boolean;
    category?: string;
    tone?: string;
}

interface VerifyResponse {
    status: string;
    tested_source_id?: string;
    tested_chunk_id?: string;
    query_used?: string;
    match_found: boolean;
    rank_of_match?: number;
    top_score: number;
    issues: string[];
}

interface DebugResult {
    contexts: DebugContext[];
    results_count: number;
    duration?: number;
}

export function ChatTab({ twinId, twinName, onSendMessage }: ChatTabProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const [showDebug, setShowDebug] = useState(false);
    const [lastDebugResult, setLastDebugResult] = useState<DebugResult | null>(null);
    const [debugLoading, setDebugLoading] = useState(false);
    const [isVerifying, setIsVerifying] = useState(false);
    const [verificationResult, setVerificationResult] = useState<VerifyResponse | null>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isTyping) return;

        const originalInput = input;
        const userMessage: Message = {
            role: 'user',
            content: input,
            timestamp: new Date()
        };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsTyping(true);
        setLastDebugResult(null); // Clear previous debug info

        // Trigger Debug Retrieval if enabled
        if (showDebug) {
            setDebugLoading(true);
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
            fetch(`${backendUrl}/debug/retrieval`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: originalInput,
                    twin_id: twinId,
                    top_k: 10
                }),
            })
                .then(res => res.json())
                .then(data => {
                    setLastDebugResult(data);
                })
                .catch(err => {
                    console.error("Debug retrieval failed", err);
                })
                .finally(() => {
                    setDebugLoading(false);
                });
        }

        try {
            // Call actual API or use provided handler
            let response: string;
            if (onSendMessage) {
                response = await onSendMessage(originalInput);
            } else {
                // Default: call backend chat API
                const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
                const res = await fetch(`${backendUrl}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        twin_id: twinId,
                        message: originalInput,
                        stream: false
                    }),
                });
                const data = await res.json();
                response = data.response || data.message || "I couldn't process that request.";
            }

            setMessages(prev => [...prev, {
                role: 'assistant',
                content: response,
                timestamp: new Date()
            }]);
        } catch (error) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: "Sorry, I encountered an error. Please try again.",
                timestamp: new Date()
            }]);
        } finally {
            setIsTyping(false);
        }
    };

    const formatTime = (date: Date) => {
        return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    };

    const runVerification = async () => {
        setIsVerifying(true);
        setVerificationResult(null);
        try {
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
            const res = await fetch(`${backendUrl}/verify/twins/${twinId}/run`, {
                method: 'POST',
            });
            const data = await res.json();
            setVerificationResult(data);
        } catch (error) {
            console.error("Verification failed", error);
        } finally {
            setIsVerifying(false);
        }
    };

    return (
        <div className="flex h-[calc(100vh-200px)]">
            {/* Main Chat Column */}
            <div className="flex-1 flex flex-col min-w-0 border-r border-white/10">
                {/* Chat Header */}
                <div className="px-6 py-4 border-b border-white/10 bg-white/5">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold">
                                {twinName.charAt(0)}
                            </div>
                            <div>
                                <h3 className="font-semibold text-white">{twinName}</h3>
                                <p className="text-xs text-slate-400">Test your twin's responses</p>
                            </div>
                        </div>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setShowDebug(!showDebug)}
                                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors border ${showDebug ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/50' : 'text-slate-400 border-transparent hover:bg-white/10'}`}
                            >
                                {showDebug ? 'Hide Debug' : 'Show Debug'}
                            </button>
                            <button
                                onClick={() => setMessages([])}
                                className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
                            >
                                Clear Chat
                            </button>
                        </div>
                    </div>
                </div>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin">
                    {messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center">
                            <div className="w-16 h-16 mb-4 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-2xl flex items-center justify-center">
                                <svg className="w-8 h-8 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-white mb-1">Start a conversation</h3>
                            <p className="text-slate-400 text-sm mb-4">Test your twin by asking questions</p>

                            <div className="flex flex-wrap justify-center gap-2 max-w-md">
                                {['What can you help me with?', 'Tell me about yourself', 'What do you know?'].map((q, i) => (
                                    <button
                                        key={i}
                                        onClick={() => setInput(q)}
                                        className="px-3 py-1.5 text-sm text-slate-300 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors"
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        messages.map((message, index) => (
                            <div
                                key={index}
                                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div className={`flex items-end gap-2 max-w-[80%] ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                    <div className={`
                    w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
                    ${message.role === 'user'
                                            ? 'bg-indigo-500'
                                            : 'bg-gradient-to-br from-purple-500 to-indigo-600'}
                    `}>
                                        {message.role === 'user' ? (
                                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                            </svg>
                                        ) : (
                                            <span className="text-white text-xs font-bold">{twinName.charAt(0)}</span>
                                        )}
                                    </div>

                                    <div className={`group relative`}>
                                        <div className={`
                        px-4 py-3 rounded-2xl
                        ${message.role === 'user'
                                                ? 'bg-indigo-500 text-white rounded-br-sm'
                                                : 'bg-white/10 text-white rounded-bl-sm'}
                    `}>
                                            {message.content}
                                        </div>
                                        <span className={`
                        absolute -bottom-5 text-[10px] text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity
                        ${message.role === 'user' ? 'right-0' : 'left-0'}
                    `}>
                                            {formatTime(message.timestamp)}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))
                    )}

                    {isTyping && (
                        <div className="flex items-end gap-2">
                            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
                                <span className="text-white text-xs font-bold">{twinName.charAt(0)}</span>
                            </div>
                            <div className="px-4 py-3 bg-white/10 rounded-2xl rounded-bl-sm">
                                <div className="flex gap-1">
                                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="p-4 border-t border-white/10 bg-white/5">
                    <form
                        onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                        className="flex gap-3"
                    >
                        <input
                            type="text"
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            placeholder="Type your message..."
                            disabled={isTyping}
                            className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all disabled:opacity-50"
                        />
                        <button
                            type="submit"
                            disabled={!input.trim() || isTyping}
                            className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        </button>
                    </form>
                </div>
            </div>

            {/* Debug Panel (Slide-in) */}
            {showDebug && (
                <div className="w-[400px] border-l border-white/10 bg-black/40 backdrop-blur-sm flex flex-col overflow-hidden transition-all">
                    <div className="px-4 py-3 border-b border-white/10 bg-white/5 flex items-center justify-between">
                        <h3 className="font-semibold text-white text-sm">Retrieval Debugging</h3>
                        <div className="flex gap-2">
                            <button
                                onClick={runVerification}
                                disabled={isVerifying}
                                className={`text-[10px] px-2 py-1 rounded font-medium transition-colors ${isVerifying
                                        ? 'bg-slate-500/20 text-slate-400 cursor-wait'
                                        : 'bg-indigo-500 hover:bg-indigo-400 text-white'
                                    }`}
                            >
                                {isVerifying ? 'Running...' : 'Verify Retrieval'}
                            </button>
                            <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded-full border border-indigo-500/30 flex items-center">
                                SIMULATOR
                            </span>
                        </div>
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
                        {/* Verification Result Panel */}
                        {(verificationResult || isVerifying) && (
                            <div className="bg-white/5 rounded-lg border border-white/10 overflow-hidden mb-4">
                                <div className="px-3 py-2 bg-white/5 border-b border-white/10 flex justify-between items-center">
                                    <span className="text-xs font-semibold text-white">Verification Status</span>
                                    {isVerifying ? (
                                        <span className="text-[10px] text-yellow-500 animate-pulse">Running...</span>
                                    ) : (
                                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${verificationResult?.status === 'PASS'
                                                ? 'bg-green-500/20 text-green-400'
                                                : 'bg-red-500/20 text-red-400'
                                            }`}>
                                            {verificationResult?.status}
                                        </span>
                                    )}
                                </div>
                                {!isVerifying && verificationResult && (
                                    <div className="p-3 space-y-2">
                                        <div className="flex justify-between text-[10px] text-slate-400">
                                            <span>Score: <span className="text-white">{verificationResult.top_score?.toFixed(4)}</span></span>
                                            <span>Match: <span className={verificationResult.match_found ? "text-green-400" : "text-red-400"}>{verificationResult.match_found ? "YES" : "NO"}</span></span>
                                        </div>
                                        {verificationResult.issues.length > 0 && (
                                            <div className="bg-red-500/10 border border-red-500/20 rounded p-2">
                                                <p className="text-[10px] font-semibold text-red-400 mb-1">Issues:</p>
                                                <ul className="list-disc list-inside text-[10px] text-red-300 space-y-0.5">
                                                    {verificationResult.issues.map((issue, i) => (
                                                        <li key={i}>{issue}</li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                        <div className="text-[10px] text-slate-500 border-t border-white/5 pt-2 mt-2">
                                            <p className="mb-1">Query Probe:</p>
                                            <code className="block bg-black/30 p-1.5 rounded text-slate-300 text-[9px] line-clamp-2">
                                                {verificationResult.query_used}
                                            </code>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {debugLoading ? (
                            <div className="flex items-center justify-center h-20 space-x-2">
                                <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse" />
                                <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse delay-75" />
                                <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-pulse delay-150" />
                            </div>
                        ) : lastDebugResult ? (
                            <div className="space-y-4">
                                <div className="flex justify-between items-center text-xs text-slate-400">
                                    <span>Found {lastDebugResult.results_count} contexts</span>
                                </div>
                                {lastDebugResult.contexts.length === 0 ? (
                                    <div className="text-center p-4 border border-dashed border-white/10 rounded-lg text-slate-500 text-sm">
                                        No relevant chunks found for this query.
                                    </div>
                                ) : (
                                    lastDebugResult.contexts.map((ctx, idx) => (
                                        <div key={idx} className="bg-white/5 rounded-lg border border-white/5 overflow-hidden">
                                            <div className="px-3 py-2 bg-white/5 border-b border-white/5 flex justify-between items-start">
                                                <div className="font-medium text-xs text-indigo-300 break-all max-w-[200px]">
                                                    {ctx.source_filename || 'Unknown Source'}
                                                </div>
                                                <div className="flex flex-col items-end">
                                                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${ctx.score > 0.7 ? 'bg-green-500/20 text-green-300' : 'bg-yellow-500/20 text-yellow-300'}`}>
                                                        Score: {typeof ctx.score === 'number' ? ctx.score.toFixed(3) : ctx.score}
                                                    </span>
                                                    {ctx.is_verified && (
                                                        <span className="text-[9px] text-green-400 mt-0.5">Verified ✅</span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="p-3">
                                                <div className="text-xs text-slate-300 leading-relaxed max-h-[150px] overflow-y-auto scrollbar-thin pr-1">
                                                    {ctx.text}
                                                </div>
                                                {ctx.category && (
                                                    <div className="mt-2 flex gap-2">
                                                        <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-slate-400">
                                                            {ctx.category}
                                                        </span>
                                                        {ctx.tone && (
                                                            <span className="text-[10px] bg-white/10 px-1.5 py-0.5 rounded text-slate-400">
                                                                {ctx.tone}
                                                            </span>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        ) : (
                            <div className="text-center p-8 text-slate-500 text-sm">
                                Send a message to see retrieval details.
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default ChatTab;
