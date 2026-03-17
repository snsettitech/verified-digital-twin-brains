'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  nameDeepResearchApi,
  type NameDeepResearchResult,
  type NameDeepResearchStatus,
} from '@/lib/api/nameDeepResearch';

const ORDERED_STAGES: NameDeepResearchStatus[] = [
  'searching',
  'crawling',
  'extracting',
  'synthesizing',
  'completed',
];

function stageIndex(status: NameDeepResearchStatus): number {
  const idx = ORDERED_STAGES.indexOf(status);
  return idx >= 0 ? idx : 0;
}

function isTerminal(status: NameDeepResearchStatus): boolean {
  return status === 'completed' || status === 'failed';
}

export default function NameOnlyDeepResearchPage() {
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [company, setCompany] = useState('');
  const [website, setWebsite] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<NameDeepResearchStatus>('created');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [stats, setStats] = useState<{
    queries_used: string[];
    urls_considered: number;
    urls_crawled: number;
    urls_blocked: number;
    sources_used_in_final: number;
    words_extracted: number;
  } | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);
  const [resultPreview, setResultPreview] = useState<NameDeepResearchResult | null>(null);
  const [resultLoadedForRunId, setResultLoadedForRunId] = useState<string | null>(null);

  const canStart = useMemo(() => name.trim().length > 0 && !busy, [name, busy]);

  const startRun = async () => {
    if (!canStart) return;
    setBusy(true);
    setError(null);
    setResultPreview(null);
    setResultLoadedForRunId(null);

    try {
      const response = await nameDeepResearchApi.createRun({
        name: name.trim(),
        hints: {
          location: location.trim() || null,
          company: company.trim() || null,
          website: website.trim() || null,
        },
        idempotency_key: `name-only-${name.trim().toLowerCase()}-${Date.now()}`,
      });
      setRunId(response.run_id);
      setStatus(response.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start research run');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!runId || isTerminal(status)) return;

    const timer = setInterval(async () => {
      try {
        const current = await nameDeepResearchApi.getRun(runId);
        setStatus(current.status);
        setStats(current.crawl_stats);
        setSelectedModel(current.selected_model);
        if (current.error_message) {
          setError(current.error_message);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Polling failed');
      }
    }, 2500);

    return () => clearInterval(timer);
  }, [runId, status]);

  useEffect(() => {
    if (!runId || status !== 'completed' || resultLoadedForRunId === runId) {
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const result = await nameDeepResearchApi.downloadResult(runId);
        if (cancelled) return;
        setResultPreview(result);
        setResultLoadedForRunId(runId);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load completed result preview');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId, status, resultLoadedForRunId]);

  const downloadJson = async () => {
    if (!runId) return;

    setBusy(true);
    try {
      const result = resultPreview ?? (await nameDeepResearchApi.downloadResult(runId));
      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `deep-research-${runId}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setBusy(false);
    }
  };

  const currentStage = stageIndex(status);

  return (
    <div className="mx-auto max-w-4xl p-6 md:p-8">
      <div className="rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h1 className="text-2xl font-bold text-white">Name to Deep Research JSON</h1>
        <p className="mt-2 text-sm text-slate-300">
          Enter a public person's name. The system will search, crawl, extract, synthesize, and produce grounded JSON with citations.
        </p>

        <div className="mt-6 grid gap-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-200">Full name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Satya Nadella"
              className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-white outline-none focus:border-cyan-400"
            />
          </label>

          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="w-fit rounded-md border border-slate-600 px-3 py-1 text-sm text-slate-200 hover:bg-slate-800"
            type="button"
          >
            Advanced {showAdvanced ? '^' : 'v'}
          </button>

          {showAdvanced && (
            <div className="grid gap-3 md:grid-cols-3">
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Location (optional)"
                className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-white outline-none focus:border-cyan-400"
              />
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Company (optional)"
                className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-white outline-none focus:border-cyan-400"
              />
              <input
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="Website (optional)"
                className="rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-white outline-none focus:border-cyan-400"
              />
            </div>
          )}

          <div>
            <button
              onClick={startRun}
              disabled={!canStart}
              className="rounded-lg bg-cyan-500 px-4 py-2 font-semibold text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? 'Starting...' : 'Start research'}
            </button>
          </div>
        </div>

        {runId && (
          <div className="mt-8 rounded-xl border border-slate-700 bg-slate-950 p-4">
            <div className="text-sm text-slate-300">Run ID: <span className="font-mono">{runId}</span></div>
            <div className="mt-3 space-y-2">
              {ORDERED_STAGES.map((stage, index) => {
                const done = index <= currentStage && status !== 'failed';
                const active = index === currentStage && !isTerminal(status);
                return (
                  <div key={stage} className="flex items-center gap-2 text-sm">
                    <span className={done ? 'text-emerald-400' : active ? 'text-cyan-400' : 'text-slate-500'}>
                      {done ? '[x]' : active ? '[~]' : '[ ]'}
                    </span>
                    <span className={done ? 'text-emerald-300' : active ? 'text-cyan-300' : 'text-slate-400'}>
                      {stage}
                    </span>
                  </div>
                );
              })}
              {status === 'failed' && <div className="text-sm text-red-400">failed</div>}
            </div>

            {stats && (
              <div className="mt-4 grid gap-2 text-xs text-slate-300 md:grid-cols-3">
                <div>URLs considered: {stats.urls_considered}</div>
                <div>URLs crawled: {stats.urls_crawled}</div>
                <div>URLs blocked: {stats.urls_blocked}</div>
                <div>Sources used: {stats.sources_used_in_final}</div>
                <div>Words extracted: {stats.words_extracted}</div>
                <div>Queries: {stats.queries_used.length}</div>
              </div>
            )}

            {selectedModel && (
              <div className="mt-3 text-xs text-slate-400">
                Model used: <span className="font-mono">{selectedModel}</span>
              </div>
            )}

            {status === 'completed' && (
              <div className="mt-4">
                <button
                  onClick={downloadJson}
                  disabled={busy}
                  className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-900 disabled:opacity-50"
                >
                  Download JSON
                </button>
              </div>
            )}
          </div>
        )}

        {resultPreview?.training_metrics && (
          <div className="mt-6 rounded-xl border border-slate-700 bg-slate-950 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Training Readiness</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
                <div className="text-xs text-slate-400">Words Processed</div>
                <div className="mt-1 text-2xl font-semibold text-white">
                  {resultPreview.training_metrics.words_processed_display}
                </div>
              </div>
              <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
                <div className="text-xs text-slate-400">Questions Answerable</div>
                <div className="mt-1 text-2xl font-semibold text-white">
                  {resultPreview.training_metrics.questions_answerable_display}
                </div>
              </div>
              <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
                <div className="text-xs text-slate-400">Mind Score</div>
                <div className="mt-1 text-2xl font-semibold text-white">
                  {resultPreview.training_metrics.mind_score}
                </div>
                <div className="text-xs text-slate-400">
                  {resultPreview.training_metrics.mind_score_label}
                </div>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-400">
              {resultPreview.training_metrics.notes}
            </p>
          </div>
        )}

        {resultPreview?.prepared_question_answers && resultPreview.prepared_question_answers.length > 0 && (
          <div className="mt-6 rounded-xl border border-slate-700 bg-slate-950 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
              Prepared Questions and Answers
            </h2>
            <div className="mt-3 space-y-3">
              {resultPreview.prepared_question_answers.map((qa, index) => (
                <div key={`${qa.question}-${index}`} className="rounded-lg border border-slate-700 bg-slate-900 p-3">
                  <div className="text-sm font-medium text-cyan-300">{qa.question}</div>
                  <div className="mt-1 text-sm text-slate-200">{qa.answer}</div>
                  <div className="mt-2 text-xs text-slate-400">
                    Citations {qa.citations.join(', ')}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-400/40 bg-red-950/30 p-3 text-sm text-red-300">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
