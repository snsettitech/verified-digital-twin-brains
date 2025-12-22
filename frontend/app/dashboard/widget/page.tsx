'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const AUTH_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN || 'development_token';
const FRONTEND_URL = process.env.NEXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000';

export default function WidgetPage() {
  const params = useParams();
  const twinId = params?.twin_id as string || 'eeeed554-9180-4229-a9af-0f8dd2c69e9b';

  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedApiKey, setSelectedApiKey] = useState<string | null>(null);
  const [domainAllowlist, setDomainAllowlist] = useState<string[]>([]);
  const [newDomain, setNewDomain] = useState('');
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'code' | 'preview'>('code');

  useEffect(() => {
    fetchApiKeys();
  }, [twinId]);

  const fetchApiKeys = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api-keys?twin_id=${twinId}`, {
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data.filter((k: any) => k.is_active));
        if (data.length > 0 && !selectedApiKey) {
          setSelectedApiKey(data[0].id);
          setDomainAllowlist(data[0].allowed_domains || []);
        }
      }
    } catch (error) {
      console.error('Error fetching API keys:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectApiKey = (keyId: string) => {
    const key = apiKeys.find(k => k.id === keyId);
    if (key) {
      setSelectedApiKey(keyId);
      setDomainAllowlist(key.allowed_domains || []);
    }
  };

  const handleAddDomain = async () => {
    if (!newDomain.trim() || !selectedApiKey) return;

    const updatedDomains = [...domainAllowlist, newDomain.trim()];

    try {
      const response = await fetch(`${API_BASE_URL}/api-keys/${selectedApiKey}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${AUTH_TOKEN}`
        },
        body: JSON.stringify({ allowed_domains: updatedDomains })
      });

      if (response.ok) {
        setDomainAllowlist(updatedDomains);
        setNewDomain('');
        await fetchApiKeys();
      }
    } catch (error) {
      console.error('Error updating domains:', error);
      alert('Failed to add domain');
    }
  };

  const handleRemoveDomain = async (domain: string) => {
    if (!selectedApiKey) return;

    const updatedDomains = domainAllowlist.filter(d => d !== domain);

    try {
      const response = await fetch(`${API_BASE_URL}/api-keys/${selectedApiKey}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${AUTH_TOKEN}`
        },
        body: JSON.stringify({ allowed_domains: updatedDomains })
      });

      if (response.ok) {
        setDomainAllowlist(updatedDomains);
        await fetchApiKeys();
      }
    } catch (error) {
      console.error('Error removing domain:', error);
      alert('Failed to remove domain');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const selectedKey = apiKeys.find(k => k.id === selectedApiKey);
  const embedCode = selectedKey ? `<!-- VT-BRAIN Chat Widget -->
<script>
  (function() {
    const script = document.createElement('script');
    script.src = '${FRONTEND_URL}/widget.js';
    script.onload = function() {
      initChatWidget({
        twinId: '${twinId}',
        apiKey: 'YOUR_API_KEY_HERE',
        apiBaseUrl: '${API_BASE_URL}'
      });
    };
    document.head.appendChild(script);
  })();
</script>` : '';

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-violet-500 via-purple-500 to-fuchsia-500 p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-1/4 w-48 h-48 bg-white/10 rounded-full blur-3xl translate-y-1/2"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold">Embed Widget</h1>
              <p className="text-white/80 text-sm">Add your twin to any website</p>
            </div>
          </div>
          <p className="text-white/70 max-w-xl">
            Configure and embed a chat widget powered by your digital twin. Just copy the code and paste it into your website.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin"></div>
        </div>
      ) : apiKeys.length === 0 ? (
        <Card className="text-center py-16">
          <CardContent>
            <div className="w-20 h-20 bg-purple-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">No API Keys Available</h3>
            <p className="text-slate-500 mb-6 max-w-md mx-auto">
              You need to create an API key before you can embed the widget.
            </p>
            <a
              href="/dashboard/api-keys"
              className="inline-block px-6 py-3 bg-gradient-to-r from-violet-500 to-purple-500 text-white rounded-xl font-semibold hover:shadow-lg transition-all"
            >
              Create API Key →
            </a>
          </CardContent>
        </Card>
      ) : (
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Configuration Panel */}
          <div className="lg:col-span-1 space-y-6">
            {/* API Key Selector */}
            <Card>
              <CardContent className="py-6">
                <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                  </svg>
                  API Key
                </h3>
                <select
                  value={selectedApiKey || ''}
                  onChange={(e) => handleSelectApiKey(e.target.value)}
                  className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-purple-500 focus:ring-0 transition-colors bg-white"
                >
                  {apiKeys.map(key => (
                    <option key={key.id} value={key.id}>
                      {key.name} ({key.key_prefix}...)
                    </option>
                  ))}
                </select>
              </CardContent>
            </Card>

            {/* Domain Allowlist */}
            <Card>
              <CardContent className="py-6">
                <h3 className="font-bold text-slate-900 mb-2 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>
                  </svg>
                  Domain Restrictions
                </h3>
                <p className="text-sm text-slate-500 mb-4">
                  Limit widget access to specific domains
                </p>

                <div className="flex gap-2 mb-4">
                  <input
                    type="text"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    placeholder="example.com"
                    className="flex-1 px-4 py-2.5 border-2 border-slate-200 rounded-xl focus:border-purple-500 focus:ring-0 transition-colors text-sm"
                    onKeyDown={(e) => e.key === 'Enter' && handleAddDomain()}
                  />
                  <button
                    onClick={handleAddDomain}
                    className="px-4 py-2.5 bg-purple-500 text-white rounded-xl font-semibold hover:bg-purple-600 transition-colors"
                  >
                    Add
                  </button>
                </div>

                {domainAllowlist.length > 0 ? (
                  <div className="space-y-2">
                    {domainAllowlist.map((domain, idx) => (
                      <div key={idx} className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg group">
                        <code className="text-sm text-slate-700">{domain}</code>
                        <button
                          onClick={() => handleRemoveDomain(domain)}
                          className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-all"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 bg-slate-50 rounded-xl">
                    <p className="text-sm text-slate-500">No restrictions — works on all domains</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Tips */}
            <div className="p-5 bg-gradient-to-br from-purple-50 to-fuchsia-50 rounded-2xl border border-purple-100">
              <h4 className="font-semibold text-purple-900 mb-3 flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path>
                </svg>
                Quick Tips
              </h4>
              <ul className="space-y-2 text-sm text-purple-800">
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-1">•</span>
                  Replace YOUR_API_KEY_HERE with your actual API key
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-1">•</span>
                  Add the code before the closing &lt;/body&gt; tag
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-400 mt-1">•</span>
                  The widget appears as a floating button
                </li>
              </ul>
            </div>
          </div>

          {/* Code & Preview Panel */}
          <div className="lg:col-span-2">
            <Card className="overflow-hidden">
              {/* Tabs */}
              <div className="flex border-b border-slate-200">
                <button
                  onClick={() => setActiveTab('code')}
                  className={`flex-1 px-6 py-4 font-semibold transition-colors ${activeTab === 'code'
                      ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50/50'
                      : 'text-slate-500 hover:text-slate-700'
                    }`}
                >
                  <svg className="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                  </svg>
                  Embed Code
                </button>
                <button
                  onClick={() => setActiveTab('preview')}
                  className={`flex-1 px-6 py-4 font-semibold transition-colors ${activeTab === 'preview'
                      ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50/50'
                      : 'text-slate-500 hover:text-slate-700'
                    }`}
                >
                  <svg className="w-5 h-5 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                  </svg>
                  Preview
                </button>
              </div>

              <CardContent className="py-6">
                {activeTab === 'code' ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <Badge variant="info">HTML / JavaScript</Badge>
                      <button
                        onClick={() => copyToClipboard(embedCode)}
                        className={`px-4 py-2 rounded-lg font-semibold transition-all ${copied
                            ? 'bg-emerald-500 text-white'
                            : 'bg-slate-900 text-white hover:bg-slate-800'
                          }`}
                      >
                        {copied ? '✓ Copied!' : 'Copy Code'}
                      </button>
                    </div>
                    <div className="relative">
                      <pre className="bg-slate-900 text-slate-100 p-6 rounded-xl overflow-x-auto text-sm leading-relaxed">
                        <code>{embedCode}</code>
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-slate-100 to-slate-50 border-2 border-slate-200 min-h-[500px]">
                    {/* Browser Chrome */}
                    <div className="bg-slate-200 px-4 py-3 flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <div className="w-3 h-3 bg-red-400 rounded-full"></div>
                        <div className="w-3 h-3 bg-yellow-400 rounded-full"></div>
                        <div className="w-3 h-3 bg-green-400 rounded-full"></div>
                      </div>
                      <div className="flex-1 mx-4">
                        <div className="bg-white rounded-lg px-4 py-1.5 text-sm text-slate-500 truncate">
                          https://your-website.com
                        </div>
                      </div>
                    </div>

                    {/* Preview Content */}
                    <div className="relative p-8 min-h-[400px]">
                      <div className="text-center mb-8">
                        <div className="w-16 h-16 bg-white rounded-2xl shadow-lg flex items-center justify-center mx-auto mb-4">
                          <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"></path>
                          </svg>
                        </div>
                        <h3 className="text-lg font-semibold text-slate-700">Your Website Content</h3>
                        <p className="text-sm text-slate-500">The widget appears as a floating button</p>
                      </div>

                      {/* Floating Widget Button */}
                      <div className="absolute bottom-6 right-6">
                        <div className="w-14 h-14 bg-gradient-to-br from-violet-500 to-purple-600 rounded-full shadow-lg shadow-purple-500/30 flex items-center justify-center animate-bounce">
                          <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path>
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
