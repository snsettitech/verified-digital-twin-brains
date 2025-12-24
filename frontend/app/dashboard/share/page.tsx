'use client';

import React, { useState, useEffect } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

export default function SharePage() {
  const [shareUrl, setShareUrl] = useState('');
  const [copied, setCopied] = useState(false);
  const [qrVisible, setQrVisible] = useState(false);
  const [shareLinks, setShareLinks] = useState<any[]>([]);
  const [isCreating, setIsCreating] = useState(false);

  const supabase = getSupabaseClient();

  const loadShareLinks = async () => {
    // Would fetch from API
    setShareLinks([
      { id: '1', name: 'Public Link', url: 'https://app.verifiedtwin.com/s/abc123', views: 245, created: '2024-01-15' },
      { id: '2', name: 'Team Access', url: 'https://app.verifiedtwin.com/s/xyz789', views: 89, created: '2024-01-20' },
    ]);
    setShareUrl(`${window.location.origin}/share/demo-twin`);
  };

  useEffect(() => {
    loadShareLinks();
  }, []);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const createNewLink = async () => {
    setIsCreating(true);
    // Would create via API
    await new Promise(r => setTimeout(r, 1000));
    const newLink = {
      id: Date.now().toString(),
      name: 'New Share Link',
      url: `${window.location.origin}/share/${Math.random().toString(36).slice(2, 10)}`,
      views: 0,
      created: new Date().toISOString().split('T')[0]
    };
    setShareLinks([newLink, ...shareLinks]);
    setIsCreating(false);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Share Your Twin</h1>
        <p className="text-slate-500 mt-1">Create shareable links for your digital twin</p>
      </div>

      {/* Quick Share */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold">Your Public Link</h2>
            <p className="text-indigo-200 text-sm">Anyone with this link can chat with your twin</p>
          </div>
          <button
            onClick={() => setQrVisible(!qrVisible)}
            className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
            </svg>
          </button>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex-1 px-4 py-3 bg-white/10 rounded-xl text-white font-mono text-sm truncate">
            {shareUrl}
          </div>
          <button
            onClick={() => copyToClipboard(shareUrl)}
            className={`px-6 py-3 rounded-xl font-semibold text-sm transition-all ${copied
              ? 'bg-emerald-500 text-white'
              : 'bg-white text-indigo-600 hover:bg-indigo-50'
              }`}
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>

        {qrVisible && (
          <div className="mt-4 p-4 bg-white rounded-xl flex items-center justify-center">
            <div className="w-32 h-32 bg-slate-200 rounded-lg flex items-center justify-center text-slate-500 text-sm">
              QR Code
            </div>
          </div>
        )}
      </div>

      {/* Share Links Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">All Share Links</h2>
          <button
            onClick={createNewLink}
            disabled={isCreating}
            className="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-xl hover:bg-slate-800 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {isCreating ? (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
            )}
            New Link
          </button>
        </div>

        <div className="divide-y divide-slate-100">
          {shareLinks.map((link) => (
            <div key={link.id} className="p-4 flex items-center gap-4 hover:bg-slate-50 transition-colors">
              <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-900">{link.name}</p>
                <p className="text-sm text-slate-500 truncate">{link.url}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium text-slate-900">{link.views} views</p>
                <p className="text-xs text-slate-400">Created {link.created}</p>
              </div>
              <button
                onClick={() => copyToClipboard(link.url)}
                className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
              <button className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Embed Options */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-slate-900 mb-4">Other Ways to Share</h2>
        <div className="grid md:grid-cols-3 gap-4">
          <a
            href="/dashboard/widget"
            className="p-4 border border-slate-200 rounded-xl hover:border-indigo-300 hover:bg-indigo-50/50 transition-all group"
          >
            <div className="w-10 h-10 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
            <p className="font-semibold text-slate-900">Embed Widget</p>
            <p className="text-sm text-slate-500 mt-1">Add chat to your website</p>
          </a>
          <a
            href="/dashboard/api-keys"
            className="p-4 border border-slate-200 rounded-xl hover:border-indigo-300 hover:bg-indigo-50/50 transition-all group"
          >
            <div className="w-10 h-10 bg-amber-100 text-amber-600 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <p className="font-semibold text-slate-900">API Access</p>
            <p className="text-sm text-slate-500 mt-1">Integrate via REST API</p>
          </a>
          <div className="p-4 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
            <div className="w-10 h-10 bg-slate-100 text-slate-400 rounded-xl flex items-center justify-center mb-3">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <p className="font-semibold text-slate-400">Slack & Discord</p>
            <p className="text-sm text-slate-400 mt-1">Coming soon</p>
          </div>
        </div>
      </div>
    </div>
  );
}
