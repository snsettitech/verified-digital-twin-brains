'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardContent } from '@/components/ui/Card';
import { Toggle } from '@/components/ui/Toggle';
import { Badge } from '@/components/ui/Badge';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const AUTH_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN || 'development_token';
const FRONTEND_URL = process.env.NEXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000';

export default function SharePage() {
  const params = useParams();
  const twinId = params?.twin_id as string || 'eeeed554-9180-4229-a9af-0f8dd2c69e9b';

  const [shareInfo, setShareInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isPublic, setIsPublic] = useState(false);

  useEffect(() => {
    fetchShareInfo();
  }, [twinId]);

  const fetchShareInfo = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/twins/${twinId}/share-link`, {
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });
      if (response.ok) {
        const data = await response.json();
        setShareInfo(data);
        setIsPublic(data?.is_public || false);
      }
    } catch (error) {
      console.error('Error fetching share info:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateToken = async () => {
    setGenerating(true);
    try {
      const response = await fetch(`${API_BASE_URL}/twins/${twinId}/share-link`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });

      if (response.ok) {
        await fetchShareInfo();
      } else {
        alert('Failed to generate share token');
      }
    } catch (error) {
      console.error('Error generating token:', error);
      alert('Failed to generate share token');
    } finally {
      setGenerating(false);
    }
  };

  const handleTogglePublic = async (checked: boolean) => {
    setIsPublic(checked);
    try {
      const response = await fetch(`${API_BASE_URL}/twins/${twinId}/sharing`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${AUTH_TOKEN}`
        },
        body: JSON.stringify({ is_public: checked })
      });

      if (!response.ok) {
        setIsPublic(!checked);
        alert('Failed to update sharing settings');
      }
    } catch (error) {
      setIsPublic(!checked);
      console.error('Error updating sharing:', error);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shareUrl = shareInfo?.share_url;

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-500 p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"></path>
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold">Share Links</h1>
              <p className="text-white/80 text-sm">Enable public access to your twin</p>
            </div>
          </div>
          <p className="text-white/70 max-w-xl">
            Create a shareable link that allows anyone to interact with your digital twin, no authentication required.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-emerald-200 border-t-emerald-600 rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="grid gap-6">
          {/* Public Sharing Toggle */}
          <Card>
            <CardContent className="py-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${isPublic ? 'bg-emerald-100' : 'bg-slate-100'
                    }`}>
                    <svg className={`w-6 h-6 transition-colors ${isPublic ? 'text-emerald-600' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900">Public Sharing</h3>
                    <p className="text-sm text-slate-500">
                      {isPublic ? 'Anyone with the link can access your twin' : 'Only authorized users can access'}
                    </p>
                  </div>
                </div>
                <Toggle checked={isPublic} onChange={handleTogglePublic} />
              </div>
            </CardContent>
          </Card>

          {/* Share Link Card */}
          <Card>
            <CardContent className="py-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">Share Link</h3>
                  <p className="text-sm text-slate-500">Your unique shareable URL</p>
                </div>
                <button
                  onClick={handleGenerateToken}
                  disabled={generating}
                  className="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-xl font-semibold hover:shadow-lg transition-all disabled:opacity-50"
                >
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                      </svg>
                      Generating...
                    </span>
                  ) : shareInfo?.share_token ? (
                    <>
                      <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                      </svg>
                      Regenerate
                    </>
                  ) : 'Generate Link'}
                </button>
              </div>

              {shareInfo?.share_token ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="flex-1 relative">
                      <input
                        type="text"
                        value={shareUrl || ''}
                        readOnly
                        className="w-full px-4 py-3.5 pr-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-mono text-sm text-slate-700"
                      />
                      <Badge variant="success" className="absolute right-3 top-1/2 -translate-y-1/2">
                        Active
                      </Badge>
                    </div>
                    <button
                      onClick={() => shareUrl && copyToClipboard(shareUrl)}
                      className={`px-6 py-3.5 rounded-xl font-semibold transition-all ${copied
                          ? 'bg-emerald-500 text-white'
                          : 'bg-slate-900 text-white hover:bg-slate-800'
                        }`}
                    >
                      {copied ? '✓ Copied!' : 'Copy URL'}
                    </button>
                  </div>

                  {/* Security Notice */}
                  <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                    <svg className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <div>
                      <p className="text-sm font-medium text-amber-800">Security Notice</p>
                      <p className="text-sm text-amber-700 mt-1">
                        This link allows anonymous public access. Only content explicitly marked as public will be accessible. Regenerating the link will invalidate the previous one.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200">
                  <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path>
                    </svg>
                  </div>
                  <h4 className="font-semibold text-slate-700 mb-2">No Share Link Generated</h4>
                  <p className="text-sm text-slate-500">Click "Generate Link" to create a public share URL</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Preview Section */}
          {shareInfo?.share_token && (
            <Card>
              <CardContent className="py-6">
                <h3 className="text-lg font-bold text-slate-900 mb-4">Preview</h3>
                <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-slate-100 to-slate-50 border-2 border-slate-200 min-h-[400px]">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <div className="w-16 h-16 bg-white rounded-2xl shadow-lg flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                        </svg>
                      </div>
                      <p className="text-slate-500 font-medium">Widget Preview</p>
                      <p className="text-sm text-slate-400 mt-1">Open the share URL to see your twin in action</p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
