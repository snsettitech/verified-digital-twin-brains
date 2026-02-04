'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import MessageList, { Message } from './MessageList';
import { useTwin } from '@/lib/context/TwinContext';
import { resolveApiBaseUrl } from '@/lib/api';

const STREAM_IDLE_TIMEOUT_MS = 60000;

export default function ChatInterface({
  twinId,
  conversationId,
  onConversationStarted,
  resetKey,
  tenantId,
  mode = 'owner',
  onMemoryUpdated
}: {
  twinId: string;
  conversationId?: string | null;
  onConversationStarted?: (id: string) => void;
  resetKey?: number;
  tenantId?: string | null;
  mode?: 'owner' | 'public' | 'training';
  onMemoryUpdated?: () => void;
}) {
  const { user } = useTwin();
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hello! I am your Verified Digital Twin. Ask me anything about your uploaded documents.",
      timestamp: Date.now(),
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastUserMessage, setLastUserMessage] = useState<string | null>(null);
  const [clarification, setClarification] = useState<any | null>(null);
  const [clarifyAnswer, setClarifyAnswer] = useState('');
  const [clarifyOption, setClarifyOption] = useState<string | null>(null);
  const [debugOpen, setDebugOpen] = useState(false);
  const [lastDebug, setLastDebug] = useState<{
    decision?: 'CLARIFY' | 'ANSWER' | 'UNKNOWN';
    used_owner_memory?: boolean;
    owner_memory_refs?: string[];
    owner_memory_topics?: string[];
    clarification_id?: string | null;
  }>({});

  const watchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const supabase = getSupabaseClient();
  const storageKey = useMemo(() => {
    const resolvedTenantId = tenantId || user?.tenant_id || 'unknown';
    return `simulator_chat_${resolvedTenantId}_${twinId}`;
  }, [tenantId, user?.tenant_id, twinId]);
  const apiBaseUrl = useMemo(() => resolveApiBaseUrl(), []);

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
            timestamp: Date.now(),
          }]);
        }
        return;
      }

      try {
        const token = await getAuthToken();
        if (!token) return;

        const response = await fetch(`${apiBaseUrl}/conversations/${conversationId}/messages`, {
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
            timestamp: Date.now(),
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
      timestamp: Date.now(),
    }]);
    setLastError(null);
    setLastUserMessage(null);
  }, [resetKey, storageKey]);

  const sendMessage = async (overrideText?: string, options?: { retry?: boolean }) => {
    const text = (overrideText ?? input).trim();
    if (!text || loading) return;

    if (!options?.retry) {
      const userMsg: Message = { role: 'user', content: text, timestamp: Date.now() };
      setMessages((prev) => [...prev, userMsg]);
      setInput('');
    }
    setClarification(null);
    setClarifyAnswer('');
    setClarifyOption(null);
    setLastUserMessage(text);
    setLastError(null);
    setLoading(true);
    setIsSearching(true);

    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      abortRef.current = new AbortController();

      const response = await fetch(`${apiBaseUrl}/chat/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: text,
          conversation_id: conversationId || null,
          mode: mode === 'training' ? 'owner' : mode,
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
      let hasReceivedBytes = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          if (!hasReceivedBytes) {
            hasReceivedBytes = true;
          }
          resetWatchdog();
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);
              if (data.type === 'clarify') {
                setIsSearching(false);
                setLoading(false);
                setClarification(data);
                const proposedTopic = data?.memory_write_proposal?.topic;
                setLastDebug({
                  decision: 'CLARIFY',
                  used_owner_memory: false,
                  owner_memory_refs: [],
                  owner_memory_topics: proposedTopic ? [proposedTopic] : [],
                  clarification_id: data.clarification_id || null
                });
                setMessages((prev) => {
                  const last = [...prev];
                  const lastMsg = { ...last[last.length - 1] };
                  lastMsg.content = data.question || 'I need clarification.';
                  last[last.length - 1] = lastMsg;
                  return last;
                });
              } else if (data.type === 'answer_metadata' || data.type === 'metadata') {
                setIsSearching(false); // Found context, now generating
                if (data.conversation_id && !conversationId && onConversationStarted) {
                  onConversationStarted(data.conversation_id);
                }
                const summaries = Array.isArray(data.owner_memory_summaries)
                  ? data.owner_memory_summaries
                  : [];
                const ownerMemoryTopics = Array.isArray(data.owner_memory_topics)
                  ? data.owner_memory_topics
                  : summaries.map((summary: any) => summary?.topic).filter(Boolean);
                const ownerMemoryRefs = Array.isArray(data.owner_memory_refs)
                  ? data.owner_memory_refs
                  : summaries.map((summary: any) => summary?.id).filter(Boolean);
                setLastDebug({
                  decision: 'ANSWER',
                  used_owner_memory: ownerMemoryRefs.length > 0,
                  owner_memory_refs: ownerMemoryRefs,
                  owner_memory_topics: ownerMemoryTopics,
                  clarification_id: null
                });
                // Extract graph_used from metadata
                const graphUsed = data.graph_context?.graph_used || false;
                setMessages((prev) => {
                  const last = [...prev];
                  const lastMsg = { ...last[last.length - 1] };
                  lastMsg.confidence_score = data.confidence_score;
                  lastMsg.citations = data.citations;
                  lastMsg.graph_used = graphUsed;
                  lastMsg.owner_memory_refs = ownerMemoryRefs;
                  lastMsg.owner_memory_topics = ownerMemoryTopics;
                  lastMsg.used_owner_memory = ownerMemoryRefs.length > 0;
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
              } else if (data.type === 'done') {
                // no-op
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
      timestamp: Date.now(),
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
        {clarification && mode !== 'public' && (
          <div className="mb-4 rounded-2xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
            <div className="font-bold text-[10px] uppercase tracking-wider mb-2">Clarification Needed</div>
            <div className="mb-2">{clarification.question}</div>
            {Array.isArray(clarification.options) && clarification.options.length > 0 && (
              <div className="flex flex-col gap-2 mb-2">
                {clarification.options.map((opt: any, idx: number) => (
                  <label key={idx} className="flex items-center gap-2 text-xs">
                    <input
                      type="radio"
                      name="clarify-option"
                      value={opt.label}
                      checked={clarifyOption === opt.label}
                      onChange={() => setClarifyOption(opt.label)}
                    />
                    <span className="font-semibold">{opt.label}</span>
                  </label>
                ))}
              </div>
            )}
            <input
              type="text"
              value={clarifyAnswer}
              onChange={(e) => setClarifyAnswer(e.target.value)}
              placeholder="Answer in one sentence..."
              className="w-full bg-white border border-indigo-200 rounded-xl px-3 py-2 text-xs mb-2"
            />
            <button
              onClick={async () => {
                try {
                  const token = await getAuthToken();
                  if (!token) throw new Error('Not authenticated');
                  const res = await fetch(`${apiBaseUrl}/twins/${twinId}/clarifications/${clarification.clarification_id}/resolve`, {
                    method: 'POST',
                    headers: {
                      'Authorization': `Bearer ${token}`,
                      'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                      answer: clarifyAnswer || clarifyOption || '',
                      selected_option: clarifyOption || undefined
                    })
                  });
                  if (!res.ok) {
                    throw new Error(`Resolve failed (${res.status})`);
                  }
                  setClarification(null);
                  setClarifyAnswer('');
                  setClarifyOption(null);
                  onMemoryUpdated?.();
                  setMessages((prev) => [...prev, { role: 'assistant', content: 'Saved. Ask again and I will answer using your memory.', timestamp: Date.now() }]);
                } catch (err) {
                  console.error(err);
                  setMessages((prev) => [...prev, { role: 'assistant', content: 'Failed to save clarification. Please retry.', timestamp: Date.now() }]);
                }
              }}
              className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-white bg-indigo-600 rounded-xl"
            >
              Save Memory
            </button>
          </div>
        )}
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
        {mode !== 'public' && (
          <div className="mb-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
            <div className="flex items-center justify-between">
              <div className="font-bold uppercase tracking-wider text-[10px] text-slate-500">Debug</div>
              <button
                onClick={() => setDebugOpen((prev) => !prev)}
                className="text-[10px] font-bold uppercase tracking-wider text-indigo-600"
              >
                {debugOpen ? 'Hide' : 'Show'}
              </button>
            </div>
            {debugOpen && (
              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap gap-3 text-[10px] text-slate-600">
                  <span>IdentityGate: <strong>{lastDebug.decision || 'UNKNOWN'}</strong></span>
                  <span>Used Owner Memory: <strong>{lastDebug.used_owner_memory ? 'Yes' : 'No'}</strong></span>
                  {lastDebug.clarification_id && (
                    <span>Clarification ID: <strong>{lastDebug.clarification_id}</strong></span>
                  )}
                </div>
                <div className="text-[10px] text-slate-600">
                  Owner Memory Topics:{' '}
                  <strong>
                    {lastDebug.owner_memory_topics && lastDebug.owner_memory_topics.length > 0
                      ? lastDebug.owner_memory_topics.join(', ')
                      : 'None'}
                  </strong>
                </div>
                <div className="text-[10px] text-slate-600">
                  Owner Memory Refs:{' '}
                  <strong>
                    {lastDebug.owner_memory_refs && lastDebug.owner_memory_refs.length > 0
                      ? lastDebug.owner_memory_refs.join(', ')
                      : 'None'}
                  </strong>
                </div>
              </div>
            )}
          </div>
        )}
        <div id="chat-input" className="relative flex items-center max-w-4xl mx-auto w-full pb-[env(safe-area-inset-bottom)]">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Ask anything about your knowledge base..."
            className="w-full bg-slate-50 border-2 border-slate-100 rounded-2xl px-6 py-5 text-sm focus:outline-none focus:ring-4 focus:ring-indigo-100 focus:border-indigo-300 transition-all pr-28 font-medium placeholder:text-slate-400"
          />
          <button
            onClick={() => sendMessage()}
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
