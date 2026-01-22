import React, { useRef, useEffect } from 'react';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: string[];
  confidence_score?: number;
  graph_used?: boolean;
}

interface MessageListProps {
  messages: Message[];
  loading: boolean;
  isSearching: boolean;
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
        <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-4 duration-500`}>
          <div className={`flex gap-4 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-10 h-10 rounded-2xl shrink-0 flex items-center justify-center text-xs font-black shadow-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white text-blue-600 border border-slate-100'
              }`}>
              {msg.role === 'user' ? 'YOU' : 'AI'}
            </div>

            <div className="space-y-3">
              <div className={`p-5 rounded-3xl text-sm leading-relaxed transition-all duration-300 ${msg.role === 'user'
                ? 'bg-gradient-to-br from-indigo-600 via-indigo-600 to-purple-600 text-white shadow-xl shadow-indigo-200/50 rounded-tr-none'
                : 'bg-white text-slate-800 border border-slate-100 shadow-lg shadow-slate-100/50 rounded-tl-none hover:shadow-xl'
                }`}>
                <p className="whitespace-pre-wrap font-medium">{msg.content}</p>
              </div>

              {msg.role === 'assistant' && (msg.citations || msg.confidence_score !== undefined || msg.graph_used) && (
                <div className="flex flex-wrap gap-2 px-1">
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
