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
  confidence?: number;
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
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
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
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
            <select
              value={form.memoryType}
              onChange={(e) => setForm((prev) => ({ ...prev, memoryType: e.target.value }))}
              className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
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
              className="md:col-span-2 rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
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
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
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
                        className="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
                      />
                    ) : (
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{row.value}</p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {editingId === row.id ? (
                        <>
                          <button
                            onClick={() => handleSaveEdit(row)}
                            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
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
      <div className="space-y-4">
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
      </div>
    </FeatureGate>
  );
}
