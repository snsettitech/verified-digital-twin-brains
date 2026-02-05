'use client';

import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  confidence_score?: number;
  graph_used?: boolean;
  owner_memory_refs?: string[];
  used_owner_memory?: boolean;
  owner_memory_topics?: string[];
  timestamp?: number; // Unix timestamp in milliseconds
}

interface MessageListProps {
  messages: Message[];
  loading: boolean;
  isSearching: boolean;
}

function formatTimestamp(ts?: number): string {
  if (!ts) return '';
  const date = new Date(ts);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  if (isToday) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
    date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function CopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-all"
      aria-label="Copy message"
      title="Copy to clipboard"
    >
      {copied ? (
        <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}

// Message reactions for AI feedback
function MessageReactions({ messageId }: { messageId: number }) {
  const [reaction, setReaction] = useState<'up' | 'down' | null>(null);

  const handleReaction = (type: 'up' | 'down') => {
    if (reaction === type) {
      setReaction(null); // Toggle off
    } else {
      setReaction(type);
      // TODO: Send reaction to backend for analytics
      console.log(`[Reaction] Message ${messageId}: ${type}`);
    }
  };

  return (
    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
      <button
        onClick={() => handleReaction('up')}
        className={`p-1 rounded transition-colors ${reaction === 'up'
          ? 'text-green-500 bg-green-50 dark:bg-green-900/30'
          : 'text-slate-400 hover:text-green-500 hover:bg-green-50 dark:hover:bg-green-900/30'
          }`}
        aria-label="Helpful response"
        title="This was helpful"
      >
        <svg className="w-4 h-4" fill={reaction === 'up' ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
        </svg>
      </button>
      <button
        onClick={() => handleReaction('down')}
        className={`p-1 rounded transition-colors ${reaction === 'down'
          ? 'text-red-500 bg-red-50 dark:bg-red-900/30'
          : 'text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30'
          }`}
        aria-label="Not helpful response"
        title="This was not helpful"
      >
        <svg className="w-4 h-4" fill={reaction === 'down' ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
        </svg>
      </button>
    </div>
  );
}

// Skeleton loader for messages
export function MessageSkeleton() {
  return (
    <div className="flex justify-start animate-pulse">
      <div className="flex gap-4 max-w-[80%]">
        <div className="w-10 h-10 rounded-2xl bg-slate-200 dark:bg-slate-700" />
        <div className="space-y-3 flex-1">
          <div className="bg-slate-200 dark:bg-slate-700 rounded-3xl rounded-tl-none p-5 space-y-2">
            <div className="h-4 bg-slate-300 dark:bg-slate-600 rounded w-3/4" />
            <div className="h-4 bg-slate-300 dark:bg-slate-600 rounded w-1/2" />
            <div className="h-4 bg-slate-300 dark:bg-slate-600 rounded w-2/3" />
          </div>
        </div>
      </div>
    </div>
  );
}

// Memoized component to prevent re-rendering of the message list when input changes.
// This improves performance significantly as the message list grows.
const MessageList = React.memo(({ messages, loading, isSearching }: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-8 bg-[#fcfcfd]">
      {messages.map((msg, idx) => (
        <div key={idx} className={`group flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
          <div className={`flex gap-4 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-10 h-10 rounded-2xl shrink-0 flex items-center justify-center text-xs font-black shadow-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white text-blue-600 border border-slate-100'
              }`}>
              {msg.role === 'user' ? 'YOU' : 'AI'}
            </div>

            <div className="space-y-3">
              <div className={`relative p-5 rounded-3xl text-sm leading-relaxed transition-all duration-300 ${msg.role === 'user'
                ? 'bg-gradient-to-br from-indigo-600 via-indigo-600 to-purple-600 text-white shadow-xl shadow-indigo-200/50 rounded-tr-none'
                : 'bg-white text-slate-800 border border-slate-100 shadow-lg shadow-slate-100/50 rounded-tl-none hover:shadow-xl'
                }`}>
                {msg.role === 'assistant' ? (
                  <div className="prose prose-sm prose-slate max-w-none prose-p:my-1 prose-headings:my-2 prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-code:text-indigo-600 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap font-medium">{msg.content}</p>
                )}

                {/* Copy button - absolute positioned */}
                {msg.content && msg.role === 'assistant' && (
                  <div className="absolute -right-2 -top-2">
                    <CopyButton content={msg.content} />
                  </div>
                )}
              </div>

              {/* Timestamp and metadata row */}
              <div className="flex items-center gap-2 px-1">
                {msg.timestamp && (
                  <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">
                    {formatTimestamp(msg.timestamp)}
                  </span>
                )}

                {msg.role === 'user' && msg.content && (
                  <CopyButton content={msg.content} />
                )}

                {msg.role === 'assistant' && (
                  <MessageReactions messageId={idx} />
                )}
              </div>

              {msg.role === 'assistant' && (msg.citations || msg.confidence_score !== undefined || msg.graph_used || msg.used_owner_memory) && (
                <div className="flex flex-wrap gap-2 px-1">
                  {msg.used_owner_memory && (
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black border uppercase tracking-wider bg-emerald-50 text-emerald-700 border-emerald-100">
                      <span>🧠</span>
                      Used Owner Memory
                    </div>
                  )}
                  {msg.used_owner_memory && msg.owner_memory_topics && msg.owner_memory_topics.length > 0 && (
                    <div className="px-3 py-1.5 rounded-full text-[10px] font-black border uppercase tracking-wider bg-emerald-50 text-emerald-700 border-emerald-100">
                      Topics: {msg.owner_memory_topics.join(', ')}
                    </div>
                  )}
                  {msg.graph_used && (
                    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black border uppercase tracking-wider bg-indigo-50 text-indigo-700 border-indigo-100">
                      <span>💡</span>
                      From your interview
                    </div>
                  )}
                  {msg.confidence_score !== undefined && (
                    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black border uppercase tracking-wider ${msg.confidence_score > 0.8 ? 'bg-green-50 text-green-700 border-green-100' : 'bg-yellow-50 text-yellow-700 border-yellow-100'
                      }`}>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                      Verified: {(msg.confidence_score * 100).toFixed(0)}%
                    </div>
                  )}
                  {msg.citations?.map((source, sIdx) => (
                    <div key={sIdx} className="bg-slate-100 text-slate-500 px-3 py-1.5 rounded-full text-[10px] font-black border border-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                      <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                      Source {sIdx + 1}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
      {loading && (
        <div className="flex justify-start animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex gap-4 max-w-[80%]">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-100 to-purple-100 border border-indigo-200/50 flex items-center justify-center shadow-lg shadow-indigo-100/50">
              <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <div className="bg-white p-5 rounded-3xl border border-slate-100 shadow-lg shadow-slate-100/50 rounded-tl-none">
              <div className="flex items-center gap-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
                <span className="text-slate-500 text-sm font-medium">
                  {isSearching ? 'Searching knowledge base...' : 'Generating response...'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
});

MessageList.displayName = 'MessageList';

export default MessageList;
