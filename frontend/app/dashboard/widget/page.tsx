'use client';

import React, { useState } from 'react';

export default function WidgetPage() {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  const [position, setPosition] = useState<'bottom-right' | 'bottom-left'>('bottom-right');
  const [primaryColor, setPrimaryColor] = useState('#6366f1');
  const [copied, setCopied] = useState(false);

  const widgetCode = `<script src="https://cdn.verifiedtwin.com/widget.js"></script>
<script>
  VerifiedTwin.init({
    twinId: 'your-twin-id',
    theme: '${theme}',
    position: '${position}',
    primaryColor: '${primaryColor}'
  });
</script>`;

  const copyCode = () => {
    navigator.clipboard.writeText(widgetCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Embed Widget</h1>
        <p className="text-slate-500 mt-1">Add a chat widget to your website</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Configuration */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
            <h2 className="text-lg font-bold text-slate-900">Customize</h2>

            {/* Theme */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">Theme</label>
              <div className="flex gap-3">
                {(['light', 'dark'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTheme(t)}
                    className={`flex-1 p-4 rounded-xl border-2 transition-all capitalize ${theme === t
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 hover:border-slate-300'
                      }`}
                  >
                    <div className={`w-full h-8 rounded-lg mb-2 ${t === 'dark' ? 'bg-slate-800' : 'bg-white border'
                      }`} />
                    <span className="text-sm font-medium text-slate-700">{t}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Position */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">Position</label>
              <div className="flex gap-3">
                {(['bottom-right', 'bottom-left'] as const).map((p) => (
                  <button
                    key={p}
                    onClick={() => setPosition(p)}
                    className={`flex-1 p-4 rounded-xl border-2 transition-all ${position === p
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 hover:border-slate-300'
                      }`}
                  >
                    <div className="w-full h-8 relative border rounded-lg bg-slate-50">
                      <div className={`absolute bottom-1 w-3 h-3 rounded bg-indigo-500 ${p === 'bottom-right' ? 'right-1' : 'left-1'
                        }`} />
                    </div>
                    <span className="text-sm font-medium text-slate-700 mt-2 block capitalize">
                      {p.replace('-', ' ')}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Color */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">Primary Color</label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-12 h-12 rounded-xl cursor-pointer border-0"
                />
                <input
                  type="text"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="flex-1 px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                />
              </div>
            </div>
          </div>

          {/* Code */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">Embed Code</h2>
              <button
                onClick={copyCode}
                className={`px-4 py-2 text-sm font-medium rounded-xl transition-all ${copied
                    ? 'bg-emerald-500 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
              >
                {copied ? 'Copied!' : 'Copy Code'}
              </button>
            </div>
            <pre className="p-4 bg-slate-900 text-slate-300 rounded-xl overflow-x-auto text-sm font-mono">
              {widgetCode}
            </pre>
            <p className="text-xs text-slate-400 mt-3">
              Add this code before the closing &lt;/body&gt; tag
            </p>
          </div>
        </div>

        {/* Preview */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-lg font-bold text-slate-900 mb-4">Preview</h2>
          <div className={`relative rounded-xl overflow-hidden h-[500px] ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
            }`}>
            {/* Mock website content */}
            <div className="p-6">
              <div className={`h-4 w-32 rounded ${theme === 'dark' ? 'bg-slate-700' : 'bg-slate-300'}`} />
              <div className={`h-3 w-48 rounded mt-3 ${theme === 'dark' ? 'bg-slate-700' : 'bg-slate-300'}`} />
              <div className={`h-3 w-40 rounded mt-2 ${theme === 'dark' ? 'bg-slate-700' : 'bg-slate-300'}`} />
            </div>

            {/* Widget Button */}
            <div className={`absolute bottom-4 ${position === 'bottom-right' ? 'right-4' : 'left-4'}`}>
              <div
                className="w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-white cursor-pointer hover:scale-110 transition-transform"
                style={{ backgroundColor: primaryColor }}
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
            </div>

            {/* Widget Panel */}
            <div className={`absolute bottom-20 ${position === 'bottom-right' ? 'right-4' : 'left-4'} w-80 rounded-2xl shadow-2xl overflow-hidden ${theme === 'dark' ? 'bg-slate-900' : 'bg-white'
              }`}>
              {/* Header */}
              <div className="p-4 flex items-center gap-3" style={{ backgroundColor: primaryColor }}>
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center text-white font-bold">
                  AI
                </div>
                <div className="text-white">
                  <p className="font-semibold">Your Twin</p>
                  <p className="text-xs opacity-80">Online</p>
                </div>
              </div>

              {/* Messages */}
              <div className={`p-4 h-32 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
                <div className={`p-3 rounded-xl text-sm ${theme === 'dark' ? 'bg-slate-800' : 'bg-slate-100'
                  }`}>
                  Hi! How can I help you today?
                </div>
              </div>

              {/* Input */}
              <div className={`p-3 border-t ${theme === 'dark' ? 'border-slate-800' : 'border-slate-100'}`}>
                <div className={`px-4 py-2 rounded-xl text-sm ${theme === 'dark' ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-400'
                  }`}>
                  Type a message...
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
