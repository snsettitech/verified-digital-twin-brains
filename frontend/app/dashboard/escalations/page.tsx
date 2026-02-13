'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';
import { useTwin } from '@/lib/context/TwinContext';
import { EmptyEscalations } from '@/components/ui/EmptyState';

export default function EscalationsPage() {
  const { getTwin, getTenant, post } = useAuthFetch();
  const { activeTwin, isLoading: twinLoading, user } = useTwin();
  const [escalations, setEscalations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [ownerAnswers, setOwnerAnswers] = useState<Record<string, string>>({});
  const [citations, setCitations] = useState<Record<string, string>>({});
  const [showPreview, setShowPreview] = useState<Record<string, boolean>>({});

  // RBAC: Check if user has admin privileges (owner role)
  const isAdmin = useMemo(() => {
    return user?.role === 'owner';
  }, [user?.role]);

  // HYBRID: Toggle between per-twin view (default) and tenant-wide admin rollup
  // RBAC: Force false for non-admins
  const [showAllTwinsRaw, setShowAllTwinsRaw] = useState(false);
  const showAllTwins = isAdmin ? showAllTwinsRaw : false;

  const twinId = activeTwin?.id;

  const fetchEscalations = useCallback(async () => {
    try {
      let response;
      if (showAllTwins || !twinId) {
        // TENANT-SCOPED: Admin rollup of all escalations
        response = await getTenant('/escalations');
      } else {
        // TWIN-SCOPED: Escalations for current twin only
        response = await getTwin(twinId, '/twins/{twinId}/escalations');
      }
      if (response.ok) {
        const data = await response.json();
        setEscalations(data);
      }
    } catch (error) {
      console.error('Error fetching escalations:', error);
    } finally {
      setLoading(false);
    }
  }, [getTwin, getTenant, twinId, showAllTwins]);

  useEffect(() => {
    if (!twinLoading) {
      fetchEscalations();
    }
  }, [twinLoading, fetchEscalations, showAllTwins]);

  const handleResolve = async (id: string) => {
    const answer = ownerAnswers[id];
    if (!answer?.trim()) return;

    setResolvingId(id);
    try {
      const response = await post(`/escalations/${id}/resolve`, { owner_answer: answer });

      if (response.ok) {
        const result = await response.json();
        // Refresh the list
        fetchEscalations();
        // Clear answer and citations for this id
        setOwnerAnswers(prev => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
        setCitations(prev => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
        setShowPreview(prev => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
    } catch (error) {
      console.error('Error resolving escalation:', error);
    } finally {
      setResolvingId(null);
    }
  };

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
            <Link href="/dashboard/escalations" className="text-sm font-bold text-blue-600 border-b-2 border-blue-600 pb-1">Escalations</Link>
            <Link href="/dashboard/verified-qna" className="text-sm font-medium text-slate-500 hover:text-slate-800">Verified QnA</Link>
            <Link href="/dashboard/settings" className="text-sm font-medium text-slate-500 hover:text-slate-800">Settings</Link>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-slate-800">Analytics</a>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full p-10">
        <h1 className="text-3xl font-extrabold tracking-tight mb-8">Escalations Queue</h1>

        {loading ? (
          <div className="flex justify-center p-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : escalations.length === 0 ? (
          <div className="bg-white rounded-3xl border border-slate-200">
            <EmptyEscalations />
          </div>
        ) : (
          <div className="space-y-4">
            {escalations.map((esc) => (
              <div key={esc.id} className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${esc.status === 'open' ? 'bg-red-50 text-red-600 border border-red-100' : 'bg-green-50 text-green-600'
                      }`}>
                      {esc.status}
                    </span>
                    <span className="text-xs text-slate-400 font-medium">
                      {new Date(esc.created_at).toLocaleString()}
                    </span>
                  </div>
                  <button className="text-blue-600 text-xs font-bold hover:underline">Review & Reply</button>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Original Question</div>
                    <div className="text-sm bg-blue-50 p-4 rounded-xl border border-blue-100 text-slate-700">
                      "{esc.user_question || esc.messages?.content}"
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Low Confidence Answer Given</div>
                    <div className="text-sm bg-red-50 p-4 rounded-xl border border-red-100 italic text-slate-600">
                      This answer had low confidence and was escalated for review.
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Confidence Score</div>
                    <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden max-w-xs">
                      <div
                        className="bg-red-500 h-full"
                        style={{ width: `${(esc.messages?.confidence_score || 0) * 100}%` }}
                      ></div>
                    </div>
                    <div className="text-[10px] font-bold text-red-600 mt-1">
                      {((esc.messages?.confidence_score || 0) * 100).toFixed(0)}%
                    </div>
                  </div>

                  {esc.status === 'open' && (
                    <div className="pt-4 mt-4 border-t border-slate-50">
                      <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Approve as Verified Answer</div>
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-600 mb-1">Question (auto-populated)</label>
                          <div className="text-sm bg-slate-50 p-3 rounded-lg border border-slate-200 text-slate-700">
                            {esc.user_question || esc.messages?.content}
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-600 mb-1">Your Verified Answer *</label>
                          <textarea
                            className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none"
                            placeholder="Provide the correct information to improve your twin..."
                            rows={4}
                            value={ownerAnswers[esc.id] || ''}
                            onChange={(e) => setOwnerAnswers({ ...ownerAnswers, [esc.id]: e.target.value })}
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-600 mb-1">Citations (optional, comma-separated source IDs)</label>
                          <input
                            type="text"
                            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                            placeholder="source1, source2, ..."
                            value={citations[esc.id] || ''}
                            onChange={(e) => setCitations({ ...citations, [esc.id]: e.target.value })}
                          />
                        </div>
                        {ownerAnswers[esc.id]?.trim() && (
                          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                            <div className="text-xs font-semibold text-green-800 mb-2">Preview:</div>
                            <div className="text-sm text-green-900">
                              <div className="font-medium mb-1">Q: {esc.user_question || esc.messages?.content}</div>
                              <div>A: {ownerAnswers[esc.id]}</div>
                            </div>
                          </div>
                        )}
                        <div className="flex justify-end gap-3">
                          <button
                            onClick={() => handleResolve(esc.id)}
                            disabled={resolvingId === esc.id || !ownerAnswers[esc.id]?.trim()}
                            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-xs font-bold py-2 px-6 rounded-lg transition-colors shadow-sm"
                          >
                            {resolvingId === esc.id ? 'Saving...' : 'Verify & Add to Memory'}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {esc.status === 'resolved' && (
                    <div className="pt-4 mt-4 border-t border-slate-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-green-600">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7"></path></svg>
                          <span className="text-[10px] font-black uppercase tracking-widest">Knowledge Verified</span>
                        </div>
                        <Link
                          href="/dashboard/verified-qna"
                          className="text-blue-600 text-xs font-bold hover:underline"
                        >
                          Edit Verified Answer →
                        </Link>
                      </div>
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
