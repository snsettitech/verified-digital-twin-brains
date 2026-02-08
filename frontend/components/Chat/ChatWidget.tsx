'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  citation_details?: Array<{
    id: string;
    filename?: string | null;
    citation_url?: string | null;
  }>;
  confidence_score?: number;
  owner_memory_refs?: string[];
}

interface ChatWidgetProps {
  twinId: string;
  apiKey?: string;
  apiBaseUrl?: string;
  theme?: {
    primaryColor?: string;
    headerColor?: string;
    headerTextColor?: string;
  };
}

export default function ChatWidget({
  twinId,
  apiKey,
  apiBaseUrl,
  theme
}: ChatWidgetProps) {
  const baseUrl = apiBaseUrl || resolveApiBaseUrl();
  const primaryColor = theme?.primaryColor || '#2563eb';
  const headerColor = theme?.headerColor || primaryColor;
  const headerTextColor = theme?.headerTextColor || '#ffffff';
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hi! I'm the digital twin. How can I help you today?",
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, loading, isOpen]);

  // Get auth token for internal dashboard use (when no API key is provided)
  const getAuthToken = useCallback(async (): Promise<string | null> => {
    try {
      const supabase = getSupabaseClient();
      const { data: { session } } = await supabase.auth.getSession();
      return session?.access_token || null;
    } catch (error) {
      console.error('Failed to get auth token:', error);
      return null;
    }
  }, []);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const assistantMsg: Message = { role: 'assistant', content: '' };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      // Use X-Twin-API-Key header if API key provided, otherwise use Supabase session
      if (apiKey) {
        headers['X-Twin-API-Key'] = apiKey;
        // Add Origin header for domain validation
        if (typeof window !== 'undefined') {
          headers['Origin'] = window.location.origin;
        }
      } else {
        // Get Supabase session token for internal dashboard use
        const token = await getAuthToken();
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
      }

      const response = await fetch(`${baseUrl}/chat/${twinId}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query: input,
          conversation_id: conversationId,
        }),
      });

      // Handle rate limit error
      if (response.status === 429) {
        const errorData = await response.json().catch(() => ({}));
        const retryAfter = response.headers.get('Retry-After');
        setMessages((prev) => {
          const last = [...prev];
          last[last.length - 1].content = `Rate limit exceeded. ${retryAfter ? `Please try again in ${retryAfter} seconds.` : 'Please try again later.'}`;
          return last;
        });
        setLoading(false);
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);
              if (data.type === 'clarify') {
                setLoading(false);
                setMessages((prev) => {
                  const last = [...prev];
                  last[last.length - 1].content = `${data.question || 'Clarification needed.'} (Queued for owner confirmation.)`;
                  return last;
                });
              } else if (data.type === 'answer_metadata' || data.type === 'metadata') {
                if (data.conversation_id && !conversationId) {
                  setConversationId(data.conversation_id);
                }
                setMessages((prev) => {
                  const last = [...prev];
                  const lastMsg = { ...last[last.length - 1] };
                  lastMsg.confidence_score = data.confidence_score;
                  lastMsg.citations = data.citations;
                  lastMsg.citation_details = data.citation_details;
                  lastMsg.owner_memory_refs = data.owner_memory_refs || [];
                  last[last.length - 1] = lastMsg;
                  return last;
                });
              } else if (data.type === 'answer_token' || data.type === 'content') {
                setMessages((prev) => {
                  const last = [...prev];
                  const lastMsg = { ...last[last.length - 1] };
                  lastMsg.content += data.content;
                  last[last.length - 1] = lastMsg;
                  return last;
                });
              }
            } catch (e) {
              console.error('Error parsing stream line:', e);
            }
          }
        }
      }
      const tail = buffer.trim();
      if (tail) {
        try {
          const data = JSON.parse(tail);
          if (data.type === 'clarify') {
            setLoading(false);
            setMessages((prev) => {
              const last = [...prev];
              last[last.length - 1].content = `${data.question || 'Clarification needed.'} (Queued for owner confirmation.)`;
              return last;
            });
          } else if (data.type === 'answer_metadata' || data.type === 'metadata') {
            if (data.conversation_id && !conversationId) {
              setConversationId(data.conversation_id);
            }
            setMessages((prev) => {
              const last = [...prev];
              const lastMsg = { ...last[last.length - 1] };
              lastMsg.confidence_score = data.confidence_score;
              lastMsg.citations = data.citations;
              lastMsg.citation_details = data.citation_details;
              lastMsg.owner_memory_refs = data.owner_memory_refs || [];
              last[last.length - 1] = lastMsg;
              return last;
            });
          } else if (data.type === 'answer_token' || data.type === 'content') {
            setMessages((prev) => {
              const last = [...prev];
              const lastMsg = { ...last[last.length - 1] };
              lastMsg.content += data.content;
              last[last.length - 1] = lastMsg;
              return last;
            });
          }
        } catch (e) {
          console.error('Error parsing stream tail:', e);
        }
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setMessages((prev) => {
        const last = [...prev];
        last[last.length - 1].content = `Sorry, I encountered an error: ${errorMessage}. Please try again.`;
        return last;
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-sans">
      {/* Chat Window */}
      {isOpen && (
        <div className="absolute bottom-20 right-0 w-80 sm:w-96 h-[500px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in slide-in-from-bottom-5 duration-300">
          {/* Header */}
          <div
            className="p-4 text-white flex items-center justify-between"
            style={{ backgroundColor: headerColor, color: headerTextColor }}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              </div>
              <div className="font-bold">Digital Twin</div>
            </div>
            <button onClick={() => setIsOpen(false)} className="hover:bg-white/10 p-1 rounded-md transition-colors">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] p-3 rounded-2xl text-sm shadow-sm ${msg.role === 'user'
                    ? 'text-white rounded-tr-none'
                    : 'bg-white text-slate-800 border border-slate-100 rounded-tl-none'
                    }`}
                  style={msg.role === 'user' ? { backgroundColor: primaryColor } : {}}
                >
                  {msg.content}
                  {msg.role === 'assistant' && msg.confidence_score !== undefined && (
                    <div className="mt-2 pt-2 border-t border-slate-100 flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400">
                      <div className={`w-1.5 h-1.5 rounded-full ${msg.confidence_score > 0.8 ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
                      Verified: {(msg.confidence_score * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white p-3 rounded-2xl border border-slate-100 text-slate-400 text-xs italic animate-pulse">
                  Thinking...
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 bg-white border-t">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Type a message..."
                className="flex-1 bg-slate-100 border-none rounded-xl px-4 py-2 text-sm outline-none"
                onFocus={(e) => {
                  e.target.style.boxShadow = `0 0 0 2px ${primaryColor}`;
                }}
                onBlur={(e) => {
                  e.target.style.boxShadow = '';
                }}
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="text-white p-2 rounded-xl disabled:bg-slate-300 transition-colors"
                style={{
                  backgroundColor: loading || !input.trim() ? undefined : primaryColor,
                }}
                onMouseEnter={(e) => {
                  if (!loading && input.trim()) {
                    e.currentTarget.style.opacity = '0.9';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!loading && input.trim()) {
                    e.currentTarget.style.opacity = '1';
                  }
                }}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-white hover:scale-110 transition-transform active:scale-95 group"
        style={{ backgroundColor: primaryColor }}
      >
        {isOpen ? (
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
        ) : (
          <div className="relative">
            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
            <span
              className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 border-2 rounded-full"
              style={{ borderColor: primaryColor }}
            ></span>
          </div>
        )}
      </button>
    </div>
  );
}
