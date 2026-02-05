'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface ApiKey {
  id: string;
  key_prefix: string;
  name: string;
  allowed_domains: string[];
  is_active: boolean;
  created_at: string;
  last_used_at?: string;
  expires_at?: string;
  group_id?: string;
}

export default function ApiKeysPage() {
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get, post, del } = useAuthFetch();
  const twinId = activeTwin?.id;

  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyDomains, setNewKeyDomains] = useState('');
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<{ key: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const fetchApiKeys = useCallback(async () => {
    if (!twinId) return;
    try {
      const response = await get(`/api-keys?twin_id=${twinId}`);
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data);
      }
    } catch (error) {
      console.error('Error fetching API keys:', error);
    } finally {
      setLoading(false);
    }
  }, [twinId, get]);

  useEffect(() => {
    if (twinId) {
      fetchApiKeys();
    } else if (!twinLoading) {
      setLoading(false);
    }
  }, [twinId, twinLoading, fetchApiKeys]);

  const handleCreateKey = async () => {
    if (!newKeyName.trim() || !twinId) return;

    setCreating(true);
    try {
      const domains = newKeyDomains.split(',').map(d => d.trim()).filter(d => d);

      const response = await post('/api-keys', {
        twin_id: twinId,
        name: newKeyName,
        allowed_domains: domains.length > 0 ? domains : undefined
      });

      if (response.ok) {
        const data = await response.json();
        setCreatedKey({ key: data.key, name: data.name });
        setNewKeyName('');
        setNewKeyDomains('');
        setShowCreateModal(false);
        await fetchApiKeys();
      } else {
        const error = await response.json();
        alert(`Failed to create API key: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error creating API key:', error);
      alert('Failed to create API key');
    } finally {
      setCreating(false);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key? It will stop working immediately.')) return;

    try {
      const response = await del(`/api-keys/${keyId}`);

      if (response.ok) {
        await fetchApiKeys();
      } else {
        alert('Failed to revoke API key');
      }
    } catch (error) {
      console.error('Error revoking API key:', error);
      alert('Failed to revoke API key');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (twinLoading) {
    return (
      <div className="flex justify-center p-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!twinId) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center max-w-md p-8">
          <div className="w-16 h-16 bg-indigo-900/50 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">No Twin Found</h2>
          <p className="text-slate-400 mb-6">Create a digital twin first to manage API keys.</p>
          <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
            Create Your Twin
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold">API Keys</h1>
              <p className="text-white/80 text-sm">Secure access to your digital twin</p>
            </div>
          </div>
          <p className="text-white/70 max-w-xl">
            Create and manage API keys for widget authentication. Each key provides secure, scoped access to your twin's capabilities.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="absolute top-8 right-8 px-6 py-2.5 bg-white text-indigo-600 rounded-xl font-semibold hover:bg-white/90 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
        >
          + Create API Key
        </button>
      </div>

      {/* Success Banner */}
      {createdKey && (
        <Card className="border-2 border-emerald-200 bg-gradient-to-r from-emerald-50 to-green-50">
          <CardContent className="py-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-emerald-900 mb-1">API Key Created Successfully!</h3>
                <p className="text-sm text-emerald-700 mb-3">
                  <strong>Important:</strong> Copy this key now. You won't be able to see it again.
                </p>
                <div className="flex items-center gap-3">
                  <code className="flex-1 px-4 py-3 bg-white rounded-xl border border-emerald-200 text-sm font-mono text-slate-800 truncate">
                    {createdKey.key}
                  </code>
                  <button
                    onClick={() => copyToClipboard(createdKey.key)}
                    className={`px-5 py-3 rounded-xl font-semibold transition-all ${copied
                      ? 'bg-emerald-500 text-white'
                      : 'bg-emerald-600 text-white hover:bg-emerald-700'
                      }`}
                  >
                    {copied ? '✓ Copied!' : 'Copy Key'}
                  </button>
                  <button
                    onClick={() => setCreatedKey(null)}
                    className="p-3 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-all"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* API Keys List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
        </div>
      ) : apiKeys.length === 0 ? (
        <Card className="text-center py-16">
          <CardContent>
            <div className="w-20 h-20 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <svg className="w-10 h-10 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">No API Keys Yet</h3>
            <p className="text-slate-500 mb-6 max-w-md mx-auto">
              Create your first API key to start embedding your digital twin on websites and applications.
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-6 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-xl font-semibold hover:shadow-lg hover:-translate-y-0.5 transition-all"
            >
              Create Your First API Key
            </button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {apiKeys.map(key => (
            <Card key={key.id} hover className="group">
              <CardContent className="py-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${key.is_active
                      ? 'bg-gradient-to-br from-indigo-100 to-purple-100'
                      : 'bg-slate-100'
                      }`}>
                      <svg className={`w-6 h-6 ${key.is_active ? 'text-indigo-600' : 'text-slate-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                      </svg>
                    </div>
                    <div>
                      <div className="flex items-center gap-3">
                        <h3 className="font-bold text-slate-900">{key.name}</h3>
                        <Badge variant={key.is_active ? 'success' : 'danger'} dot>
                          {key.is_active ? 'Active' : 'Revoked'}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 mt-1">
                        <code className="text-sm text-slate-500 font-mono">{key.key_prefix}...</code>
                        <span className="text-sm text-slate-400">•</span>
                        <span className="text-sm text-slate-500">
                          {key.allowed_domains.length > 0
                            ? `${key.allowed_domains.length} domain(s)`
                            : 'All domains'}
                        </span>
                        <span className="text-sm text-slate-400">•</span>
                        <span className="text-sm text-slate-500">
                          Last used: {key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    {key.is_active && (
                      <button
                        onClick={() => handleRevokeKey(key.id)}
                        className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-xl font-medium transition-all"
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create API Key"
      >
        <div className="space-y-5">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Name</label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="My Widget Key"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-indigo-500 focus:ring-0 transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">
              Allowed Domains <span className="font-normal text-slate-400">(optional)</span>
            </label>
            <input
              type="text"
              value={newKeyDomains}
              onChange={(e) => setNewKeyDomains(e.target.value)}
              placeholder="example.com, *.example.com"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-indigo-500 focus:ring-0 transition-colors"
            />
            <p className="text-xs text-slate-500 mt-2">
              Leave empty to allow all domains. Use wildcards for subdomains.
            </p>
          </div>
          <div className="flex gap-3 pt-4">
            <button
              onClick={() => setShowCreateModal(false)}
              className="flex-1 px-4 py-3 border-2 border-slate-200 text-slate-700 rounded-xl font-semibold hover:bg-slate-50 transition-colors"
              disabled={creating}
            >
              Cancel
            </button>
            <button
              onClick={handleCreateKey}
              className="flex-1 px-4 py-3 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-xl font-semibold hover:shadow-lg transition-all disabled:opacity-50"
              disabled={creating || !newKeyName.trim()}
            >
              {creating ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Creating...
                </span>
              ) : 'Create Key'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
