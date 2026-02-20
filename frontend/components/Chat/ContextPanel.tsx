'use client';

import React from 'react';

interface ContextPanelProps {
  snapshot: {
    queryClass?: string;
    answerabilityState?: string;
    plannerAction?: string;
    confidenceScore?: number;
    citations?: string[];
    citationDetails?: Array<{
      id: string;
      filename?: string | null;
      citation_url?: string | null;
    }>;
    usedOwnerMemory?: boolean;
    ownerMemoryTopics?: string[];
    retrievalStats?: Record<string, any>;
    selectedEvidenceBlockTypes?: string[];
  } | null;
}

function renderPercent(value: unknown): string {
  const num = Number(value);
  if (Number.isNaN(num)) return 'n/a';
  return `${Math.round(num * 100)}%`;
}

export default function ContextPanel({ snapshot }: ContextPanelProps) {
  const citations: Array<{ id: string; filename?: string | null; citation_url?: string | null }> =
    snapshot?.citationDetails?.length
    ? snapshot?.citationDetails
    : (snapshot?.citations || []).map((id) => ({ id }));
  const retrievalStats = snapshot?.retrievalStats || {};
  const blockCounts = retrievalStats?.evidence_block_counts || {};

  return (
    <aside
      data-testid="context-panel"
      className="w-full xl:w-[360px] xl:shrink-0 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-bold text-slate-900">What I Used</h2>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Read-only</span>
      </div>

      <div className="space-y-3 text-xs">
        <section className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Planner</div>
          <div className="mt-1 text-slate-700">Class: <strong>{snapshot?.queryClass || 'unknown'}</strong></div>
          <div className="text-slate-700">Answerability: <strong>{snapshot?.answerabilityState || 'unknown'}</strong></div>
          <div className="text-slate-700">Action: <strong>{snapshot?.plannerAction || 'unknown'}</strong></div>
          <div className="text-slate-700">
            Confidence: <strong>{snapshot?.confidenceScore !== undefined ? renderPercent(snapshot?.confidenceScore) : 'n/a'}</strong>
          </div>
        </section>

        <section className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Evidence Mix</div>
          <div className="mt-1 text-slate-700">Chunks: <strong>{retrievalStats?.chunk_count ?? 0}</strong></div>
          <div className="text-slate-700">Dense Top1: <strong>{Number(retrievalStats?.dense_top1 || 0).toFixed(3)}</strong></div>
          <div className="text-slate-700">Rerank Top1: <strong>{Number(retrievalStats?.rerank_top1 || 0).toFixed(3)}</strong></div>
          <div className="mt-1 text-slate-700">
            Block types:
            <div className="mt-1 flex flex-wrap gap-1">
              {(snapshot?.selectedEvidenceBlockTypes || []).length > 0 ? (
                (snapshot?.selectedEvidenceBlockTypes || []).map((block) => (
                  <span key={block} className="rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">
                    {block}
                  </span>
                ))
              ) : (
                <span className="text-slate-500">none</span>
              )}
            </div>
            {Object.keys(blockCounts).length > 0 && (
              <div className="mt-2 text-[10px] text-slate-500">
                {Object.entries(blockCounts).map(([k, v]) => `${k}: ${v}`).join(' | ')}
              </div>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Memory</div>
          <div className="mt-1 text-slate-700">
            Used owner memory: <strong>{snapshot?.usedOwnerMemory ? 'yes' : 'no'}</strong>
          </div>
          <div className="text-slate-700">
            Topics: <strong>{(snapshot?.ownerMemoryTopics || []).join(', ') || 'none'}</strong>
          </div>
        </section>

        <section className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Citations</div>
          {citations.length === 0 ? (
            <div className="mt-1 text-slate-500">No citations yet.</div>
          ) : (
            <ul className="mt-1 space-y-1">
              {citations.slice(0, 8).map((item, idx) => (
                <li key={`${item.id}-${idx}`} className="truncate text-slate-700">
                  {item.citation_url ? (
                    <a
                      href={item.citation_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-indigo-700 hover:underline"
                    >
                      {item.filename || item.id}
                    </a>
                  ) : (
                    <span>{item.filename || item.id}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </aside>
  );
}
