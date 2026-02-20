'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import FeatureGate from '@/components/ui/FeatureGate';
import { useTwin } from '@/lib/context/TwinContext';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';
import { isRuntimeFeatureEnabled } from '@/lib/features/runtimeFlags';

type SourceRow = {
  id: string;
  filename: string;
  status?: string;
};

type MemoryRow = {
  id: string;
  topic_normalized: string;
  memory_type: string;
  value: string;
  status?: string;
};

type PublishControls = {
  published_identity_topics: string[];
  published_policy_topics: string[];
  published_source_ids: string[];
};

const POLICY_TYPES = new Set(['stance', 'lens', 'tone_rule']);

export default function PublishControlsPage() {
  const enabled = isRuntimeFeatureEnabled('publishControls');
  const { activeTwin, refreshTwins } = useTwin();
  const { get, patch } = useAuthFetch();

  const twinId = activeTwin?.id;
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [memories, setMemories] = useState<MemoryRow[]>([]);
  const [controls, setControls] = useState<PublishControls>({
    published_identity_topics: [],
    published_policy_topics: [],
    published_source_ids: [],
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const identityMemories = useMemo(
    () => memories.filter((row) => row.memory_type === 'belief' || row.memory_type === 'preference'),
    [memories],
  );
  const policyMemories = useMemo(
    () => memories.filter((row) => POLICY_TYPES.has(row.memory_type)),
    [memories],
  );

  const loadData = useCallback(async () => {
    if (!twinId) return;
    setLoading(true);
    setError(null);
    try {
      const [sourceRes, memoryRes] = await Promise.all([
        get(`/sources/${twinId}`),
        get(`/twins/${twinId}/owner-memory?status=all`),
      ]);

      if (sourceRes.ok) {
        const sourceData = await sourceRes.json();
        setSources(Array.isArray(sourceData) ? sourceData : []);
      } else {
        setSources([]);
      }

      if (memoryRes.ok) {
        const memoryData = await memoryRes.json();
        setMemories(Array.isArray(memoryData) ? memoryData : []);
      } else {
        setMemories([]);
      }

      const settings = (activeTwin?.settings || {}) as Record<string, any>;
      const existing = (settings.publish_controls || {}) as Partial<PublishControls>;
      setControls({
        published_identity_topics: Array.isArray(existing.published_identity_topics)
          ? existing.published_identity_topics
          : [],
        published_policy_topics: Array.isArray(existing.published_policy_topics)
          ? existing.published_policy_topics
          : [],
        published_source_ids: Array.isArray(existing.published_source_ids)
          ? existing.published_source_ids
          : [],
      });
    } catch (err: any) {
      setError(err?.message || 'Failed to load publish controls.');
    } finally {
      setLoading(false);
    }
  }, [get, twinId, activeTwin?.settings]);

  useEffect(() => {
    if (twinId) {
      void loadData();
    }
  }, [twinId, loadData]);

  const toggleListItem = (key: keyof PublishControls, value: string) => {
    setControls((prev) => {
      const set = new Set(prev[key]);
      if (set.has(value)) set.delete(value);
      else set.add(value);
      return { ...prev, [key]: Array.from(set) };
    });
  };

  const save = async () => {
    if (!twinId) return;
    setSaving(true);
    setError(null);
    try {
      const currentSettings = (activeTwin?.settings || {}) as Record<string, any>;
      const nextSettings = {
        ...currentSettings,
        publish_controls: {
          ...controls,
          updated_at: new Date().toISOString(),
        },
      };
      const res = await patch(`/twins/${twinId}`, { settings: nextSettings });
      if (!res.ok) {
        throw new Error(`Failed to save publish controls (${res.status})`);
      }
      await refreshTwins();
    } catch (err: any) {
      setError(err?.message || 'Failed to save publish controls.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <FeatureGate
      enabled={enabled}
      title="Publish Controls"
      description="Enable NEXT_PUBLIC_FF_PUBLISH_CONTROLS to manage office-hours published subsets."
    >
      <div className="space-y-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900">Publish Controls</h1>
          <p className="mt-1 text-sm text-slate-600">
            Choose exactly what external share users can access: published identity, policies, and sources only.
          </p>
        </div>
        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
        ) : null}
        {loading ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600">Loading...</div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Published Identity</h2>
              <p className="mt-1 text-xs text-slate-500">Used for “who are you” style queries in share mode.</p>
              <div className="mt-3 space-y-2">
                {identityMemories.length === 0 ? (
                  <div className="text-xs text-slate-500">No identity memories available.</div>
                ) : (
                  identityMemories.map((row) => (
                    <label key={row.id} className="flex items-start gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={controls.published_identity_topics.includes(row.topic_normalized)}
                        onChange={() => toggleListItem('published_identity_topics', row.topic_normalized)}
                      />
                      <span>{row.topic_normalized}</span>
                    </label>
                  ))
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Published Policies</h2>
              <p className="mt-1 text-xs text-slate-500">Used for boundary/policy responses in share mode.</p>
              <div className="mt-3 space-y-2">
                {policyMemories.length === 0 ? (
                  <div className="text-xs text-slate-500">No policy memories available.</div>
                ) : (
                  policyMemories.map((row) => (
                    <label key={row.id} className="flex items-start gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={controls.published_policy_topics.includes(row.topic_normalized)}
                        onChange={() => toggleListItem('published_policy_topics', row.topic_normalized)}
                      />
                      <span>{row.topic_normalized}</span>
                    </label>
                  ))
                )}
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Published Sources</h2>
              <p className="mt-1 text-xs text-slate-500">Only these source IDs are eligible for public citations.</p>
              <div className="mt-3 max-h-[320px] space-y-2 overflow-y-auto">
                {sources.length === 0 ? (
                  <div className="text-xs text-slate-500">No sources available.</div>
                ) : (
                  sources.map((row) => (
                    <label key={row.id} className="flex items-start gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={controls.published_source_ids.includes(row.id)}
                        onChange={() => toggleListItem('published_source_ids', row.id)}
                      />
                      <span className="truncate">{row.filename}</span>
                    </label>
                  ))
                )}
              </div>
            </section>
          </div>
        )}

        <button
          onClick={save}
          disabled={saving || !twinId}
          className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Publish Controls'}
        </button>
      </div>
    </FeatureGate>
  );
}

