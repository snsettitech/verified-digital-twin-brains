'use client';

import React, { useCallback, useEffect, useState } from 'react';
import FeatureGate from '@/components/ui/FeatureGate';
import { isRuntimeFeatureEnabled } from '@/lib/features/runtimeFlags';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

type OwnerMemory = {
  id: string;
  topic_normalized: string;
  memory_type: string;
  value: string;
  status?: string;
  provenance?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
};

const MEMORY_TYPES = ['belief', 'preference', 'stance', 'lens', 'tone_rule'];

export default function MemoryCenterPage() {
  const { activeTwin, isLoading: twinLoading } = useTwin();
  const { get, post, patch, del } = useAuthFetch();
  const enabled = isRuntimeFeatureEnabled('memoryCenter');

  const [rows, setRows] = useState<OwnerMemory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState('');
  const [form, setForm] = useState({
    topic: '',
    memoryType: 'belief',
    value: '',
    identitySafe: false,
  });

  const twinId = activeTwin?.id;

  const fetchRows = useCallback(async () => {
    if (!twinId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await get(`/twins/${twinId}/owner-memory?status=all`);
      if (!res.ok) {
        throw new Error(`Failed to load memories (${res.status})`);
      }
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load memories.');
    } finally {
      setLoading(false);
    }
  }, [get, twinId]);

  useEffect(() => {
    if (!twinLoading && twinId) {
      void fetchRows();
    }
  }, [twinLoading, twinId, fetchRows]);

  const handleCreate = async () => {
    if (!twinId) return;
    if (!form.topic.trim() || !form.value.trim()) {
      setError('Topic and value are required.');
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const res = await post(`/twins/${twinId}/owner-memory`, {
        topic_normalized: form.topic.trim(),
        memory_type: form.memoryType,
        value: form.value.trim(),
        identity_safe: form.identitySafe,
        source_label: 'explicit_ui',
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to create memory (${res.status})`);
      }
      setForm({ topic: '', memoryType: 'belief', value: '', identitySafe: false });
      await fetchRows();
    } catch (err: any) {
      setError(err?.message || 'Failed to create memory.');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (memoryId: string) => {
    if (!twinId) return;
    setError(null);
    try {
      const res = await del(`/twins/${twinId}/owner-memory/${memoryId}`);
      if (!res.ok) {
        throw new Error(`Failed to delete memory (${res.status})`);
      }
      setRows((prev) => prev.filter((row) => row.id !== memoryId));
    } catch (err: any) {
      setError(err?.message || 'Failed to delete memory.');
    }
  };

  const handleToggleLock = async (row: OwnerMemory) => {
    if (!twinId) return;
    const currentlyLocked = Boolean(row.provenance?.locked);
    setError(null);
    try {
      const res = await post(`/twins/${twinId}/owner-memory/${row.id}/lock`, { locked: !currentlyLocked });
      if (!res.ok) {
        throw new Error(`Lock endpoint unavailable (${res.status}).`);
      }
      await fetchRows();
    } catch (err: any) {
      setError(err?.message || 'Failed to toggle lock.');
    }
  };

  const startEdit = (row: OwnerMemory) => {
    setEditingId(row.id);
    setEditDraft(row.value);
    setError(null);
  };

  const handleSaveEdit = async (row: OwnerMemory) => {
    if (!twinId || !editingId) return;
    setError(null);
    try {
      const res = await patch(`/twins/${twinId}/owner-memory/${row.id}`, {
        topic_normalized: row.topic_normalized,
        memory_type: row.memory_type,
        value: editDraft.trim(),
      });
      if (!res.ok) {
        throw new Error(`Failed to update memory (${res.status})`);
      }
      setEditingId(null);
      setEditDraft('');
      await fetchRows();
    } catch (err: any) {
      setError(err?.message || 'Failed to update memory.');
    }
  };

  const content = (() => {
    if (twinLoading) {
      return (
        <div className="flex min-h-[420px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        </div>
      );
    }
    if (!twinId) {
      return (
        <div className="rounded-2xl border border-slate-200 bg-white p-8">
          <h2 className="text-xl font-bold text-slate-900">No Twin Selected</h2>
          <p className="mt-2 text-sm text-slate-600">Select a twin from the sidebar to manage memory.</p>
        </div>
      );
    }
    return (
      <div className="space-y-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Add Memory (Explicit Only)</h2>
          <p className="mt-1 text-xs text-slate-500">
            Memories are written only via this form or explicit owner actions. Assistant auto-write is disabled.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <input
              data-testid="memory-topic-input"
              value={form.topic}
              onChange={(e) => setForm((prev) => ({ ...prev, topic: e.target.value }))}
              placeholder="Topic (e.g., remote work, pricing)"
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
            />
            <select
              value={form.memoryType}
              onChange={(e) => setForm((prev) => ({ ...prev, memoryType: e.target.value }))}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
            >
              {MEMORY_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            <textarea
              data-testid="memory-value-input"
              value={form.value}
              onChange={(e) => setForm((prev) => ({ ...prev, value: e.target.value }))}
              placeholder="Memory value"
              className="md:col-span-2 rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
              rows={3}
            />
            <label className="md:col-span-2 flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.identitySafe}
                onChange={(e) => setForm((prev) => ({ ...prev, identitySafe: e.target.checked }))}
              />
              Mark as identity-safe
            </label>
          </div>
          <div className="mt-4">
            <button
              data-testid="memory-save-button"
              onClick={handleCreate}
              disabled={creating}
              className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'Saving...' : 'Save Memory'}
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Stored Memories</h2>
          {loading ? (
            <div className="mt-4 text-sm text-slate-500">Loading...</div>
          ) : rows.length === 0 ? (
            <div className="mt-4 text-sm text-slate-500">No memories found yet.</div>
          ) : (
            <div className="mt-4 space-y-3">
              {rows.map((row) => {
                const locked = Boolean(row.provenance?.locked);
                return (
                  <div key={row.id} className="rounded-xl border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-semibold text-slate-900">{row.topic_normalized}</div>
                      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider">
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{row.memory_type}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{row.status || 'unknown'}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">
                          identity_safe:{String(Boolean(row.provenance?.identity_safe))}
                        </span>
                      </div>
                    </div>
                    {editingId === row.id ? (
                      <textarea
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        rows={3}
                        className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
                      />
                    ) : (
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{row.value}</p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {editingId === row.id ? (
                        <>
                          <button
                            onClick={() => handleSaveEdit(row)}
                            className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
                          >
                            Save
                          </button>
                          <button
                            onClick={() => {
                              setEditingId(null);
                              setEditDraft('');
                            }}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => startEdit(row)}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            Correct
                          </button>
                          <button
                            onClick={() => handleToggleLock(row)}
                            className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                              locked
                                ? 'border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                                : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                            }`}
                          >
                            {locked ? 'Unlock' : 'Lock'}
                          </button>
                          <button
                            onClick={() => handleDelete(row.id)}
                            className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-100"
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  })();

  return (
    <FeatureGate
      enabled={enabled}
      title="Memory Center"
      description="Enable NEXT_PUBLIC_FF_MEMORY_CENTER to manage explicit owner memory."
    >
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Memory Center</h1>
          <p className="mt-1 text-sm text-slate-600">
            Explicit-only memory management with provenance labels and identity-safe controls.
          </p>
        </div>
        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        {content}

        {/* ─── Graph Memory — Early Access ─── */}
        <div className="rounded-2xl border border-amber-200/60 bg-amber-50/50 p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-amber-100 border border-amber-200/60">
                <svg className="h-5 w-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-slate-900">Knowledge Graph</h2>
                  <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-600">
                    Early Access
                  </span>
                </div>
                <p className="mt-0.5 text-sm text-slate-500">Structured memory of your beliefs, decisions, and knowledge connections.</p>
              </div>
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              { label: 'Belief Nodes', desc: 'Core positions and values your persona holds with evidence.' },
              { label: 'Decision Graph', desc: 'How you approach tradeoffs — surfaced in every answer.' },
              { label: 'Concept Links', desc: 'Relationships between your areas of expertise.' },
            ].map(({ label, desc }) => (
              <div key={label} className="rounded-[14px] border border-amber-200/50 bg-white p-4">
                <p className="text-sm font-semibold text-slate-800">{label}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{desc}</p>
                <p className="mt-3 text-xs font-semibold text-amber-500">Coming soon</p>
              </div>
            ))}
          </div>

          <p className="mt-4 text-xs leading-5 text-slate-400">
            Knowledge Graph is being built on Neo4j + Graphiti. It will become the long-term memory layer that makes your persona richer over time. Early access notifications will be sent to your registered email.
          </p>
        </div>
      </div>
    </FeatureGate>
  );
}
