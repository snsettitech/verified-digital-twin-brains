'use client';

import React, { useState, useRef, useEffect } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    confidence_score?: number;
    extracted_data?: any;
}

export default function InterviewInterface({
    twinId,
    onGraphUpdate
}: {
    twinId: string;
    onGraphUpdate: () => void;
}) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'assistant',
            content: "Hello! I am your Cognitive Host. I'm here to learn how you think. Let's start building your decision model.",
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [conversationId, setConversationId] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const supabase = getSupabaseClient();

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, loading]);

    const getAuthToken = async (): Promise<string | null> => {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token || null;
    };

    const sendMessage = async () => {
        if (!input.trim() || loading) return;

        const userMsg: Message = { role: 'user', content: input };
        setMessages((prev) => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            const token = await getAuthToken();
            if (!token) {
                throw new Error('Not authenticated');
            }

            const response = await fetch(`${API_BASE_URL}/cognitive/interview/${twinId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: userMsg.content,
                    conversation_id: conversationId,
                }),
            });

            if (!response.ok) throw new Error('Network response was not ok');

            const data = await response.json();

            // Update Conversation ID if new
            if (data.conversation_id && !conversationId) {
                setConversationId(data.conversation_id);
            }

            // Add Assistant Message
            const assistantMsg: Message = {
                role: 'assistant',
                content: data.response,
                confidence_score: data.confidence,
                extracted_data: data.extracted_data
            };

            setMessages((prev) => [...prev, assistantMsg]);

            // Look for extracted entities/relationships and notify parent
            if (data.extracted_data && (data.extracted_data.nodes?.length > 0 || data.extracted_data.edges?.length > 0)) {
                onGraphUpdate();
            }

        } catch (error: any) {
            console.error('Error sending message:', error);
            setMessages((prev) => [...prev, {
                role: 'assistant',
                content: "Sorry, I'm having trouble connecting to the Host Engine right now."
            }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-white rounded-3xl shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden relative">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#fcfcfd]">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                        <div className={`flex gap-3 max-w-[90%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                            <div className={`w-8 h-8 rounded-xl shrink-0 flex items-center justify-center text-[10px] font-black shadow-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-gradient-to-br from-indigo-500 to-purple-600 text-white'
                                }`}>
                                {msg.role === 'user' ? 'YOU' : 'HOST'}
                            </div>

                            <div className="space-y-2">
                                <div className={`p-4 rounded-2xl text-sm leading-relaxed ${msg.role === 'user'
                                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100 rounded-tr-none'
                                    : 'bg-white text-slate-800 border border-slate-100 shadow-sm rounded-tl-none'
                                    }`}>
                                    <p className="whitespace-pre-wrap">{msg.content}</p>
                                </div>

                                {/* Scribe Extraction Badge */}
                                {msg.extracted_data && (msg.extracted_data.nodes?.length > 0) && (
                                    <div className="flex flex-wrap gap-2 px-1">
                                        <div className="bg-purple-50 text-purple-700 px-2 py-1 rounded-lg text-[10px] font-black border border-purple-100 uppercase tracking-wider flex items-center gap-1">
                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                                            Extracted {msg.extracted_data.nodes.length} Concepts
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="flex gap-3 max-w-[80%]">
                            <div className="w-8 h-8 rounded-xl bg-white border border-slate-100 flex items-center justify-center shadow-sm">
                                <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                            </div>
                            <div className="bg-white p-4 rounded-2xl border border-slate-100 text-slate-400 text-xs shadow-sm rounded-tl-none italic">
                                Host is analyzing...
                            </div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 bg-white border-t border-slate-50">
                <div className="relative flex items-center w-full">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                        placeholder="Type your response..."
                        className="w-full bg-slate-50 border-none rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-100 transition-all pr-20 font-medium"
                    />
                    <button
                        onClick={sendMessage}
                        disabled={loading || !input.trim()}
                        className="absolute right-1.5 bg-indigo-600 text-white px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wide hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-all"
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}
