'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useTwin } from '@/lib/context/TwinContext';
import { createClient } from '@/lib/supabase/client';
import { resolveApiBaseUrl } from '@/lib/api';

export default function SharePage() {
  const { activeTwin, refreshTwins } = useTwin();
  const [isUpdating, setIsUpdating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [qrVisible, setQrVisible] = useState(false);

  const apiBaseUrl = useMemo(() => resolveApiBaseUrl(), []);
  const supabase = createClient();

  const settings = (activeTwin?.settings || {}) as any;
  const widgetSettings = settings.widget_settings || {};
  const isPublic = widgetSettings.public_share_enabled || false;
  const handle = settings.handle || '';
  const shareToken = widgetSettings.share_token || '';

  const shareUrl = useMemo(() => {
    if (typeof window === 'undefined') return '';
    const origin = window.location.origin;
    if (handle) return `${origin}/share/${handle}`;
    if (activeTwin?.id && shareToken) return `${origin}/share/${activeTwin.id}/${shareToken}`;
    return '';
  }, [handle, activeTwin, shareToken]);

  const copyToClipboard = (text: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const togglePublicShare = async () => {
    if (!activeTwin) return;
    setIsUpdating(true);
    try {
      // We use the patch endpoint to update settings
      const newStatus = !isPublic;

      const response = await fetch(`${apiBaseUrl}/twins/${activeTwin.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          is_public: newStatus
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update share status');
      }

      await refreshTwins();
    } catch (error) {
      console.error('Error toggling share:', error);
      alert('Failed to update sharing status. Please try again.');
    } finally {
      setIsUpdating(false);
    }
  };

  if (!activeTwin) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354l1.1 3.356h3.526l-2.853 2.073 1.1 3.356-2.853-2.073-2.853 2.073 1.1-3.356-2.853-2.073h3.526L12 4.354z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-slate-900">Select a Twin</h2>
          <p className="text-slate-500">Please select a twin from the sidebar to manage sharing.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Share Your Twin</h1>
        <p className="text-slate-500 mt-1">Manage public access and sharing for {activeTwin.name}</p>
      </div>

      {/* Primary Share Link */}
      <div className={`rounded-3xl p-8 text-white transition-all duration-500 ${isPublic ? 'bg-gradient-to-br from-indigo-600 via-purple-600 to-pink-600 shadow-xl shadow-indigo-500/20' : 'bg-slate-800'}`}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${isPublic ? 'bg-emerald-500 text-white' : 'bg-slate-600 text-slate-300'}`}>
                {isPublic ? 'Public' : 'Private'}
              </span>
              <h2 className="text-xl font-bold">Public Chat Link</h2>
            </div>
            <p className={`${isPublic ? 'text-indigo-100' : 'text-slate-400'} text-sm max-w-md`}>
              {isPublic
                ? 'Anyone with this link can interact with your digital twin. Perfect for your website or social bio.'
                : 'Sharing is currently disabled. Enable it to allow others to chat with your twin.'}
            </p>
          </div>
          <button
            onClick={togglePublicShare}
            disabled={isUpdating}
            className={`px-6 py-3 rounded-2xl font-bold text-sm transition-all flex items-center gap-2 shadow-lg ${isPublic
              ? 'bg-white text-indigo-600 hover:bg-slate-50'
              : 'bg-indigo-600 text-white hover:bg-indigo-500'}`}
          >
            {isUpdating ? (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : isPublic ? (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"></path></svg>
                Disable Sharing
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path></svg>
                Enable Sharing
              </>
            )}
          </button>
        </div>

        {isPublic && (
          <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
            <div className="flex-1 px-4 py-4 bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl text-white font-mono text-sm break-all">
              {shareUrl}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => copyToClipboard(shareUrl)}
                className={`flex-1 md:flex-none px-8 py-4 rounded-2xl font-bold text-sm transition-all ${copied
                  ? 'bg-emerald-500 text-white'
                  : 'bg-white text-slate-900 hover:bg-slate-100 shadow-xl'
                  }`}
              >
                {copied ? 'Copied!' : 'Copy Link'}
              </button>
              <button
                onClick={() => setQrVisible(!qrVisible)}
                className="p-4 bg-white/10 hover:bg-white/20 rounded-2xl transition-colors border border-white/20"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {isPublic && qrVisible && (
          <div className="mt-6 p-6 bg-white rounded-3xl flex flex-col items-center justify-center animate-in fade-in slide-in-from-top-4">
            <div className="w-48 h-48 bg-white rounded-2xl flex items-center justify-center mb-4 border-2 border-slate-200 p-2">
              {shareUrl ? (
                <img 
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(shareUrl)}`}
                  alt="QR Code"
                  className="w-full h-full"
                  onError={(e) => {
                    // Fallback if API fails
                    const target = e.target as HTMLImageElement;
                    target.style.display = 'none';
                    target.parentElement!.innerHTML = `
                      <div class="w-full h-full flex items-center justify-center text-slate-400">
                        <svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                        </svg>
                      </div>
                    `;
                  }}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-400">
                  <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                  </svg>
                </div>
              )}
            </div>
            <p className="text-slate-500 font-medium">Scan to chat with {activeTwin?.name || 'your twin'}</p>
          </div>
        )}
      </div>

      {/* Sharing Options Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-3xl border border-slate-200 p-6 flex flex-col items-start text-left group hover:shadow-lg transition-all">
          <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Embed Widget</h3>
          <p className="text-slate-500 text-sm mb-6">Add a floating chat bubble to your personal website or blog with just one line of code.</p>
          <a href="/dashboard/widget" className="mt-auto px-4 py-2 bg-slate-900 text-white text-sm font-bold rounded-xl hover:bg-slate-800 transition-colors">
            Get Embed Code
          </a>
        </div>

        <div className="bg-white rounded-3xl border border-slate-200 p-6 flex flex-col items-start text-left group hover:shadow-lg transition-all">
          <div className="w-12 h-12 bg-purple-50 text-purple-600 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Custom Handle</h3>
          <p className="text-slate-500 text-sm mb-6">Current handle: <span className="font-mono font-bold text-indigo-600">@{handle || 'none'}</span>. Update your handle in settings to customize your share URL.</p>
          <a href="/dashboard/settings" className="mt-auto px-4 py-2 bg-slate-100 text-slate-700 text-sm font-bold rounded-xl hover:bg-slate-200 transition-colors">
            Change Handle
          </a>
        </div>
      </div>

      {/* Advanced Sharing */}
      <div className="bg-slate-50 rounded-3xl p-8 border border-white border-opacity-50">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-10 h-10 bg-amber-100 text-amber-600 rounded-xl flex items-center justify-center">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Developer Access</h3>
            <p className="text-slate-500 text-sm">Integrate your twin into custom applications via our API.</p>
          </div>
        </div>
        <div className="flex gap-4">
          <a href="/dashboard/api-keys" className="px-4 py-2 bg-white text-slate-900 border border-slate-200 text-sm font-bold rounded-xl hover:bg-slate-50 transition-colors shadow-sm">
            API Documentation
          </a>
          <a href="/dashboard/api-keys" className="px-4 py-2 text-indigo-600 text-sm font-bold rounded-xl hover:underline">
            Manage API Keys →
          </a>
        </div>
      </div>
    </div>
  );
}
