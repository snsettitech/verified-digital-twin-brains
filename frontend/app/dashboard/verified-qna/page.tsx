'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface VerifiedQnA {
  id: string;
  question: string;
  answer: string;
  created_at: string;
  updated_at?: string;
  citations?: Array<{ id: string; source_id?: string; citation_url?: string }>;
  patches?: Array<{ id: string; previous_answer: string; new_answer: string; reason?: string; patched_at: string }>;
  groups?: Array<{ id: string; name: string }>;
}

export default function VerifiedQnAPage() {
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get, patch, del } = useAuthFetch();
  const [qnaList, setQnaList] = useState<VerifiedQnA[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editAnswer, setEditAnswer] = useState('');
  const [editReason, setEditReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const twinId = activeTwin?.id;

  const fetchVerifiedQnA = useCallback(async () => {
    if (!twinId) return;
    try {
      const response = await get(`/twins/${twinId}/verified-qna`);
      if (response.ok) {
        const data = await response.json();
        // Fetch group information for each QnA
        const qnaWithGroups = await Promise.all(
          data.map(async (qna: VerifiedQnA) => {
            try {
              const groupsRes = await get(`/content/verified_qna/${qna.id}/groups`);
              if (groupsRes.ok) {
                const groups = await groupsRes.json();
                return { ...qna, groups };
              }
            } catch (e) {
              console.error(`Error fetching groups for QnA ${qna.id}:`, e);
            }
            return { ...qna, groups: [] };
          })
        );
        setQnaList(qnaWithGroups);
      }
    } catch (error) {
      console.error('Error fetching verified QnA:', error);
    } finally {
      setLoading(false);
    }
  }, [twinId, get]);

  useEffect(() => {
    if (twinId) {
      fetchVerifiedQnA();
    } else if (!twinLoading) {
      setLoading(false);
    }
  }, [twinId, twinLoading, fetchVerifiedQnA]);

  const handleEdit = (qna: VerifiedQnA) => {
    setEditingId(qna.id);
    setEditAnswer(qna.answer);
    setEditReason('');
  };

  const handleSaveEdit = async (id: string) => {
    if (!editAnswer.trim() || !editReason.trim()) return;

    setSaving(true);
    try {
      const response = await patch(`/verified-qna/${id}`, {
        answer: editAnswer,
        reason: editReason
      });

      if (response.ok) {
        await fetchVerifiedQnA();
        setEditingId(null);
        setEditAnswer('');
        setEditReason('');
      }
    } catch (error) {
      console.error('Error updating verified QnA:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this verified answer?')) return;

    try {
      const response = await del(`/verified-qna/${id}`);
      if (response.ok) {
        await fetchVerifiedQnA();
      }
    } catch (error) {
      console.error('Error deleting verified QnA:', error);
    }
  };

  const filteredQna = qnaList.filter(qna =>
    qna.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
    qna.answer.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (twinLoading) {
    return (
      <div className="flex justify-center p-20">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!twinId) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center max-w-md p-8">
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">No Twin Found</h2>
          <p className="text-slate-500 mb-6">Create a digital twin first to manage verified Q&A.</p>
          <a href="/dashboard/right-brain" className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition-colors">
            Create Your Twin
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#f8fafc] text-slate-900 font-sans">
      <header className="sticky top-0 z-10 bg-white border-b px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/dashboard" className="text-xl font-black tracking-tighter text-blue-600 hover:opacity-80 transition-opacity">
            VT-BRAIN
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            <Link href="/dashboard" className="text-sm font-medium text-slate-500 hover:text-slate-800">Chat</Link>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-slate-800">Knowledge Base</a>
            <Link href="/dashboard/verified-qna" className="text-sm font-bold text-blue-600 border-b-2 border-blue-600 pb-1">Verified QnA</Link>
            <Link href="/dashboard/settings" className="text-sm font-medium text-slate-500 hover:text-slate-800">Settings</Link>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-slate-800">Analytics</a>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto w-full p-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight">Verified QnA</h1>
          <div className="flex items-center gap-4">
            <input
              type="text"
              placeholder="Search questions or answers..."
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center p-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : filteredQna.length === 0 ? (
          <div className="bg-white p-20 rounded-3xl border border-dashed flex flex-col items-center text-center">
            <div className="w-16 h-16 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mb-4">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-slate-800">No verified QnA entries</h3>
            <p className="text-slate-500 max-w-sm mt-2">
              {searchQuery ? 'No entries match your search.' : 'Verified answers will appear here once you add them.'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filteredQna.map((qna) => (
              <div key={qna.id} className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Question</div>
                    <div className="text-sm font-semibold text-slate-800 mb-4">{qna.question}</div>

                    {editingId === qna.id ? (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-600 mb-1">Answer</label>
                          <textarea
                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none"
                            rows={4}
                            value={editAnswer}
                            onChange={(e) => setEditAnswer(e.target.value)}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-600 mb-1">Reason for Edit *</label>
                          <input
                            type="text"
                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                            placeholder="Why are you editing this answer?"
                            value={editReason}
                            onChange={(e) => setEditReason(e.target.value)}
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleSaveEdit(qna.id)}
                            disabled={saving || !editAnswer.trim() || !editReason.trim()}
                            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-xs font-bold py-2 px-4 rounded-lg transition-colors"
                          >
                            {saving ? 'Saving...' : 'Save Changes'}
                          </button>
                          <button
                            onClick={() => {
                              setEditingId(null);
                              setEditAnswer('');
                              setEditReason('');
                            }}
                            className="bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold py-2 px-4 rounded-lg transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Answer</div>
                        <div className="text-sm text-slate-700 mb-4">{qna.answer}</div>

                        <div className="flex items-center gap-4 text-xs text-slate-500">
                          <span>Created: {new Date(qna.created_at).toLocaleDateString()}</span>
                          {qna.updated_at && qna.updated_at !== qna.created_at && (
                            <span>Updated: {new Date(qna.updated_at).toLocaleDateString()}</span>
                          )}
                        </div>

                        {qna.citations && qna.citations.length > 0 && (
                          <div className="mt-4">
                            <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Citations</div>
                            <div className="flex flex-wrap gap-2">
                              {qna.citations.map((citation, idx) => (
                                <span
                                  key={citation.id || idx}
                                  className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded border border-blue-200"
                                >
                                  {citation.source_id || citation.citation_url || 'Citation'}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {qna.patches && qna.patches.length > 0 && (
                          <div className="mt-4">
                            <button
                              onClick={() => setExpandedId(expandedId === qna.id ? null : qna.id)}
                              className="text-xs font-semibold text-blue-600 hover:underline"
                            >
                              {expandedId === qna.id ? 'Hide' : 'Show'} Edit History ({qna.patches.length})
                            </button>
                            {expandedId === qna.id && (
                              <div className="mt-2 space-y-2 border-t border-slate-100 pt-2">
                                {qna.patches.map((patchItem) => (
                                  <div key={patchItem.id} className="text-xs bg-slate-50 p-3 rounded-lg">
                                    <div className="font-semibold text-slate-700 mb-1">
                                      {new Date(patchItem.patched_at).toLocaleString()}
                                    </div>
                                    {patchItem.reason && (
                                      <div className="text-slate-600 mb-2">Reason: {patchItem.reason}</div>
                                    )}
                                    <div className="text-slate-500">
                                      <div className="line-through mb-1">{patchItem.previous_answer.substring(0, 100)}...</div>
                                      <div>{patchItem.new_answer.substring(0, 100)}...</div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {editingId !== qna.id && (
                    <div className="flex gap-2 ml-4">
                      <button
                        onClick={() => handleEdit(qna)}
                        className="text-blue-600 text-xs font-bold hover:underline px-3 py-1"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDelete(qna.id)}
                        className="text-red-600 text-xs font-bold hover:underline px-3 py-1"
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
