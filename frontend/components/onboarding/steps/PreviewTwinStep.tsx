'use client';

import React, { useState, useRef, useEffect } from 'react';
import { WizardStep } from '../Wizard';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

interface Message {
    role: 'user' | 'assistant';
    content: string;
}

interface PreviewTwinStepProps {
    twinId: string | null;
    twinName: string;
    tagline?: string;
}

export function PreviewTwinStep({
    twinId,
    twinName,
    tagline
}: PreviewTwinStepProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'assistant',
            content: `Hi! I'm ${twinName}${tagline ? `, ${tagline}` : ''}. Ask me anything to see how I'll respond!`
        }
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setIsLoading(true);

        try {
            if (twinId) {
                const response = await authFetchStandalone(`/chat/${twinId}`, {
                    method: 'POST',
                    body: JSON.stringify({
                        query: userMessage,
                        mode: 'owner',
                    }),
                });

                if (!response.ok || !response.body) {
                    throw new Error(`Chat request failed (${response.status})`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                let assistantContent = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() ?? '';

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.type === 'clarify') {
                                assistantContent =
                                    data.question || 'I need clarification before I can answer that confidently.';
                                break;
                            }
                            if (data.type === 'content' || data.type === 'answer_token') {
                                const token = typeof data.token === 'string'
                                    ? data.token
                                    : typeof data.content === 'string'
                                        ? data.content
                                        : '';
                                assistantContent += token;
                            }
                        } catch {
                            // Skip malformed NDJSON lines.
                        }
                    }
                }

                if (buffer.trim()) {
                    try {
                        const data = JSON.parse(buffer.trim());
                        if (data.type === 'clarify') {
                            assistantContent =
                                data.question || 'I need clarification before I can answer that confidently.';
                        } else if (data.type === 'content' || data.type === 'answer_token') {
                            const token = typeof data.token === 'string'
                                ? data.token
                                : typeof data.content === 'string'
                                    ? data.content
                                    : '';
                            assistantContent += token;
                        }
                    } catch {
                        // Ignore trailing partial/invalid payload.
                    }
                }

                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: assistantContent || "I'm still learning. Once you launch me, I'll be able to answer based on your knowledge!",
                }]);
            } else {
                // Simulated response for preview
                await new Promise(resolve => setTimeout(resolve, 1000));
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: "I'm still being configured! Once you complete setup and launch me, I'll be able to give you real answers based on all the knowledge you've shared. 🚀"
                }]);
            }
        } catch (error) {
            // Fallback response
            await new Promise(resolve => setTimeout(resolve, 500));
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: "Great question! Once I'm launched, I'll answer based on your verified knowledge. For now, this is just a preview of how our conversations will look."
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const initials = twinName
        .split(' ')
        .map(n => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || '?';

    return (
        <WizardStep
            title="Preview Your Twin"
            description="Test a conversation before launching"
        >
            <div className="max-w-2xl mx-auto">
                {/* Chat Container */}
                <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
                    {/* Header */}
                    <div className="p-4 border-b border-white/10 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-sm font-bold text-white">
                            {initials}
                        </div>
                        <div>
                            <p className="font-semibold text-white">{twinName}</p>
                            <div className="flex items-center gap-1.5">
                                <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                                <span className="text-xs text-emerald-400 font-medium">Preview Mode</span>
                            </div>
                        </div>
                    </div>

                    {/* Messages */}
                    <div className="h-80 overflow-y-auto p-4 space-y-4">
                        {messages.map((message, index) => (
                            <div
                                key={index}
                                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div
                                    className={`
                                        max-w-[80%] px-4 py-3 rounded-2xl text-sm
                                        ${message.role === 'user'
                                            ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-br-md'
                                            : 'bg-white/10 text-slate-200 rounded-bl-md'
                                        }
                                    `}
                                >
                                    {message.content}
                                </div>
                            </div>
                        ))}

                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-white/10 px-4 py-3 rounded-2xl rounded-bl-md">
                                    <div className="flex gap-1">
                                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div className="p-4 border-t border-white/10">
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder="Try asking a question..."
                                className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-sm"
                            />
                            <button
                                onClick={sendMessage}
                                disabled={!input.trim() || isLoading}
                                className="px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-xl hover:from-indigo-500 hover:to-purple-500 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Suggestions */}
                <div className="mt-4 flex flex-wrap gap-2 justify-center">
                    <p className="text-xs text-slate-500 w-full text-center mb-2">Try asking:</p>
                    {['What is your background?', 'What do you specialize in?', 'How can you help me?'].map((suggestion) => (
                        <button
                            key={suggestion}
                            onClick={() => setInput(suggestion)}
                            className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-full text-xs text-slate-400 hover:bg-white/10 hover:text-white transition-all"
                        >
                            {suggestion}
                        </button>
                    ))}
                </div>
            </div>
        </WizardStep>
    );
}
