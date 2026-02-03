'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import MessageList, { Message } from './MessageList';
import { useTwin } from '@/lib/context/TwinContext';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const STREAM_IDLE_TIMEOUT_MS = 20000;

export default function ChatInterface({
  twinId,
  conversationId,
  onConversationStarted,
  resetKey
}: {
  twinId: string;
  conversationId?: string | null;
  onConversationStarted?: (id: string) => void;
  resetKey?: number;
}) {
  const { user } = useTwin();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hello! I am your Verified Digital Twin. Ask me anything about your uploaded documents.",
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);

  const watchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const supabase = getSupabaseClient();
  const storageKey = useMemo(() => {
    const tenantId = user?.tenant_id || 'unknown';
    return `simulator_chat_${tenantId}_${twinId}`;
  }, [user?.tenant_id, twinId]);

  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  }, [supabase]);

  const persistMessages = useCallback((nextMessages: Message[]) => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(nextMessages));
    } catch {
      // ignore storage errors
    }
  }, [storageKey]);

  const resetWatchdog = useCallback(() => {
    if (watchdogRef.current) {
      clearTimeout(watchdogRef.current);
    }
    watchdogRef.current = setTimeout(() => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
    }, STREAM_IDLE_TIMEOUT_MS);
  }, []);

  const clearWatchdog = useCallback(() => {
    if (watchdogRef.current) {
      clearTimeout(watchdogRef.current);
      watchdogRef.current = null;
    }
  }, []);

  useEffect(() => {
    const loadHistory = async () => {
      setLastError(null);
      if (!conversationId) {
        let restored = false;
        try {
          const raw = localStorage.getItem(storageKey);
          if (raw) {
            const parsed = JSON.parse(raw) as Message[];
            if (Array.isArray(parsed) && parsed.length > 0) {
              setMessages(parsed);
              restored = true;
            }
          }
        } catch {
          // ignore storage parse errors
        }
        if (!restored) {
          setMessages([{
            role: 'assistant',
            content: "Hello! I am your Verified Digital Twin. Ask me anything about your uploaded documents.",
          }]);
        }
        return;
      }

      try {
        const token = await getAuthToken();
        if (!token) return;

        const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (response.ok) {
          const data = await response.json();
          const history = data.map((m: any) => ({
            role: m.role,
            content: m.content,
            citations: m.citations,
            confidence_score: m.confidence_score
          }));
          setMessages(history.length > 0 ? history : [{
            role: 'assistant',
            content: "Hello! I am your Verified Digital Twin. Ask me anything about your uploaded documents.",
          }]);
        }
      } catch (error) {
        console.error('Error loading history:', error);
      }
    };
    loadHistory();
  }, [conversationId, getAuthToken, storageKey]);

  useEffect(() => {
    persistMessages(messages);
  }, [messages, persistMessages]);

  useEffect(() => {
    if (!resetKey) return;
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // ignore storage errors
    }
    setMessages([{
      role: 'assistant',
      content: "Hello! I am your Verified Digital Twin. Ask me anything about your uploaded documents.",
    }]);
    setLastError(null);
    setLastUserMessage(null);
  }, [resetKey, storageKey]);

  const sendMessage = async (overrideText?: string, options?: { retry?: boolean }) => {
    const text = (overrideText ?? input).trim();
    if (!text || loading) return;

    if (!options?.retry) {
      const userMsg: Message = { role: 'user', content: text };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
    }
    setLastUserMessage(text);
    setLastError(null);
    setLoading(true);
    setIsSearching(true);

    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      abortRef.current = new AbortController();
      resetWatchdog();

      const response = await fetch(`${API_BASE_URL}/chat/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: text,
          conversation_id: conversationId || null,
        }),
        signal: abortRef.current.signal
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          resetWatchdog();
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);
              if (data.type === 'metadata') {
                setIsSearching(false); // Found context, now generating
                if (data.conversation_id && !conversationId && onConversationStarted) {
                  onConversationStarted(data.conversation_id);
                }
                // Extract graph_used from metadata
                const graphUsed = data.graph_context?.graph_used || false;
                setMessages((prev) => {
                  const last = [...prev];
                  const lastMsg = { ...last[last.length - 1] };
                  lastMsg.confidence_score = data.confidence_score;
                  lastMsg.citations = data.citations;
                  lastMsg.graph_used = graphUsed;
                  last[last.length - 1] = lastMsg;
                  return last;
                });
              } else if (data.type === 'content') {
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
    } catch (error: any) {
      console.error('Error sending message:', error);
      const message = error?.name === 'AbortError'
        ? 'Connection stalled. Please retry.'
        : (error?.message || "Sorry, I'm having trouble connecting to my brain right now.");
      setLastError(message);
      setMessages((prev) => {
        const last = [...prev];
        last[last.length - 1] = {
          role: 'assistant',
          content: message
        };
        return last;
      });
    } finally {
      clearWatchdog();
      abortRef.current = null;
      setLoading(false);
      setIsSearching(false);
    }
  };

  const retryLastMessage = async () => {
    if (!lastUserMessage || loading) return;
    await sendMessage(lastUserMessage, { retry: true });
  };

  const clearHistory = () => {
    const confirmed = window.confirm('Clear this chat history for the current twin?');
    if (!confirmed) return;
    try {
      localStorage.removeItem(storageKey);
    } catch {
      // ignore storage errors
    }
    setMessages([{
      role: 'assistant',
      content: "Hello! I am your Verified Digital Twin. Ask me anything about your uploaded documents.",
    }]);
    setLastError(null);
    setLastUserMessage(null);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] w-full bg-gradient-to-b from-white to-slate-50 rounded-3xl shadow-2xl shadow-slate-200/50 border border-slate-100/50 overflow-hidden backdrop-blur-sm">
      {/* Header */}
      <div className="px-8 py-6 bg-white border-b flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-blue-200">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            </div>
            <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 border-4 border-white rounded-full"></div>
          </div>
          <div>
            <div className="font-black text-slate-800 tracking-tight">Verified Digital Twin</div>
            <div className="text-[10px] uppercase font-bold text-slate-400 tracking-widest flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
              Live Knowledge Base
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={clearHistory}
            className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500 hover:text-slate-800 hover:bg-slate-50 rounded-xl transition-all border border-slate-100"
          >
            Clear history
          </button>
          <button className="p-2.5 text-slate-400 hover:text-slate-800 hover:bg-slate-50 rounded-xl transition-all">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"></path></svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={messages} loading={loading} isSearching={isSearching} />

      {/* Input */}
      <div className="p-6 bg-white/80 backdrop-blur-sm border-t border-slate-100">
        {lastError && (
          <div className="mb-4 flex items-center justify-between gap-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <span>{lastError}</span>
            <button
              onClick={retryLastMessage}
              className="rounded-xl border border-rose-200 bg-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-rose-600 hover:bg-rose-100"
            >
              Retry
            </button>
          </div>
        )}
        <div className="relative flex items-center max-w-4xl mx-auto w-full">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Ask anything about your knowledge base..."
            className="w-full bg-slate-50 border-2 border-slate-100 rounded-2xl px-6 py-5 text-sm focus:outline-none focus:ring-4 focus:ring-indigo-100 focus:border-indigo-300 transition-all pr-28 font-medium placeholder:text-slate-400"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="absolute right-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-3.5 rounded-xl text-xs font-bold uppercase tracking-wider hover:from-indigo-700 hover:to-purple-700 disabled:from-slate-300 disabled:to-slate-400 disabled:cursor-not-allowed transition-all shadow-lg shadow-indigo-200/50 active:scale-95 flex items-center gap-2"
          >
            <span>Send</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
          </button>
        </div>
        <div className="mt-4 flex items-center justify-center gap-2 text-[10px] text-slate-400 font-medium">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          <span>Powered by verified knowledge • End-to-end encrypted</span>
        </div>
      </div>
    </div>
  );
}
