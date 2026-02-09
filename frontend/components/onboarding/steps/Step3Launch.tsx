'use client';

import React, { useState } from 'react';

interface Step3LaunchProps {
  twinId: string | null;
  twinName: string;
  handle: string;
  tagline: string;
  specialization: string;
  isLaunching: boolean;
  onLaunch: () => Promise<void>;
}

const SPECIALIZATION_ICONS: Record<string, string> = {
  vanilla: '🧠',
  founder: '🚀',
  creator: '🎨',
  technical: '⚡',
};

export default function Step3Launch({
  twinId,
  twinName,
  handle,
  tagline,
  specialization,
  isLaunching,
  onLaunch,
}: Step3LaunchProps) {
  const [activeTab, setActiveTab] = useState<'preview' | 'test' | 'settings'>('preview');
  const [testMessage, setTestMessage] = useState('');
  const [testResponse, setTestResponse] = useState('');
  const [isTesting, setIsTesting] = useState(false);

  const handleTest = async () => {
    if (!testMessage || !twinId) return;
    setIsTesting(true);
    
    // Simulate test - in real implementation, this would call the chat API
    setTimeout(() => {
      setTestResponse(`Hello! I'm ${twinName || 'your digital twin'}. I'm here to help answer questions based on my training. This is a preview of how I'll respond to your audience.`);
      setIsTesting(false);
    }, 1500);
  };

  const shareUrl = typeof window !== 'undefined' && twinId 
    ? `${window.location.origin}/share/${twinId}`
    : '';

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Silent fail
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">Ready to Launch!</h2>
        <p className="text-slate-400">Preview your twin and make it public</p>
      </div>

      {/* Twin Card Preview */}
      <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-2xl p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl">
            {SPECIALIZATION_ICONS[specialization] || '🧠'}
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold text-white">{twinName || 'Your Digital Twin'}</h3>
            {tagline && <p className="text-slate-400 text-sm">{tagline}</p>}
            {handle && (
              <p className="text-indigo-400 text-sm">@{handle}</p>
            )}
          </div>
          <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-medium rounded-full">
            Ready
          </span>
        </div>

        {/* Stats Preview */}
        <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-white/10">
          <div className="text-center">
            <p className="text-2xl font-bold text-white">98%</p>
            <p className="text-xs text-slate-400">Accuracy</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-white">&lt;2s</p>
            <p className="text-xs text-slate-400">Response</p>
          </div>
          <div className="text-center">
            <p className="text-2xl font-bold text-white">24/7</p>
            <p className="text-xs text-slate-400">Available</p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 p-1 bg-white/5 rounded-xl">
        <button
          onClick={() => setActiveTab('preview')}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'preview'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
          }`}
        >
          👁️ Preview
        </button>
        <button
          onClick={() => setActiveTab('test')}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'test'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
          }`}
        >
          💬 Test Chat
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
            activeTab === 'settings'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-400 hover:text-white hover:bg-white/5'
          }`}
        >
          ⚙️ Share
        </button>
      </div>

      {/* Preview Tab */}
      {activeTab === 'preview' && (
        <div className="space-y-4 animate-fadeIn">
          <div className="bg-white/5 rounded-2xl p-6 border border-white/10">
            <h4 className="font-semibold text-white mb-4">What your visitors will see</h4>
            
            {/* Mock Public Page */}
            <div className="bg-[#0a0a0f] rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xl">
                  {SPECIALIZATION_ICONS[specialization] || '🧠'}
                </div>
                <div>
                  <h5 className="font-semibold text-white">{twinName || 'Your Digital Twin'}</h5>
                  <p className="text-xs text-slate-400">Verified Digital Twin</p>
                </div>
              </div>
              
              <div className="bg-white/5 rounded-xl p-3 mb-3">
                <p className="text-slate-300 text-sm">Hi! I&apos;m an AI version of {twinName}. Ask me anything!</p>
              </div>

              <div className="flex gap-2 flex-wrap">
                <span className="px-3 py-1 bg-white/5 text-slate-400 text-xs rounded-full">
                  What can you help with?
                </span>
                <span className="px-3 py-1 bg-white/5 text-slate-400 text-xs rounded-full">
                  Tell me about yourself
                </span>
              </div>

              <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                Online now
              </div>
            </div>
          </div>

          <div className="p-4 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
            <p className="text-indigo-300 text-sm">
              <span className="font-semibold">💡 Tip:</span> Your twin will improve as more people interact with it. You can review and approve answers in the dashboard.
            </p>
          </div>
        </div>
      )}

      {/* Test Chat Tab */}
      {activeTab === 'test' && (
        <div className="space-y-4 animate-fadeIn">
          <div className="bg-white/5 rounded-2xl p-4 border border-white/10">
            {testResponse ? (
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-600 flex items-center justify-center text-xs">You</div>
                  <div className="flex-1 p-3 bg-white/10 rounded-xl">
                    <p className="text-white text-sm">{testMessage}</p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs">🤖</div>
                  <div className="flex-1 p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
                    <p className="text-white text-sm">{testResponse}</p>
                  </div>
                </div>
                <button
                  onClick={() => {
                    setTestResponse('');
                    setTestMessage('');
                  }}
                  className="w-full py-2 text-sm text-slate-400 hover:text-white transition-colors"
                >
                  Ask another question
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-slate-400 text-sm">Test how your twin responds:</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={testMessage}
                    onChange={(e) => setTestMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleTest()}
                    placeholder="Ask something..."
                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                  />
                  <button
                    onClick={handleTest}
                    disabled={!testMessage || isTesting}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors"
                  >
                    {isTesting ? (
                      <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                    ) : (
                      'Send'
                    )}
                  </button>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {['What do you know?', 'Tell me about yourself', 'What can you help with?'].map((q) => (
                    <button
                      key={q}
                      onClick={() => setTestMessage(q)}
                      className="px-3 py-1 bg-white/5 hover:bg-white/10 text-slate-400 text-xs rounded-lg transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="space-y-4 animate-fadeIn">
          {twinId && (
            <div className="space-y-3">
              <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                <label className="block text-sm font-medium text-slate-300 mb-2">Share Link</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={shareUrl}
                    readOnly
                    className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white text-sm"
                  />
                  <button
                    onClick={() => copyToClipboard(shareUrl)}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium transition-colors"
                  >
                    Copy
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => copyToClipboard(`<iframe src="${shareUrl}/embed" width="100%" height="600" frameborder="0"></iframe>`)}
                  className="p-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-colors text-left"
                >
                  <span className="text-2xl mb-2 block">🌐</span>
                  <p className="font-medium text-white text-sm">Embed Widget</p>
                  <p className="text-xs text-slate-400">Add to your website</p>
                </button>
                <button
                  onClick={() => copyToClipboard(shareUrl)}
                  className="p-4 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl transition-colors text-left"
                >
                  <span className="text-2xl mb-2 block">🔗</span>
                  <p className="font-medium text-white text-sm">Direct Link</p>
                  <p className="text-xs text-slate-400">Share anywhere</p>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Launch Button */}
      <div className="pt-4 border-t border-white/10">
        <button
          onClick={onLaunch}
          disabled={isLaunching || !twinId}
          className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold rounded-xl shadow-lg shadow-indigo-500/25 transition-all flex items-center justify-center gap-2"
        >
          {isLaunching ? (
            <>
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Launching...
            </>
          ) : (
            <>
              🚀 Launch My Digital Twin
            </>
          )}
        </button>
        <p className="text-center text-slate-500 text-sm mt-3">
          You can always edit your twin later in the dashboard
        </p>
      </div>
    </div>
  );
}
