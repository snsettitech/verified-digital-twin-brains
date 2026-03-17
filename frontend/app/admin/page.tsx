'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

type HealthState = 'healthy' | 'degraded' | 'unhealthy' | 'checking';

interface TwinSummary {
  id: string;
  name: string;
}

interface SystemHealth {
  status: string;
  services: {
    pinecone: string;
    openai: string;
    neo4j: string;
  };
}

interface VersionInfo {
  git_sha?: string;
  environment?: string;
  build_time?: string;
  service?: string;
  version?: string;
}

interface GraphOutboxJob {
  id: string;
  operation: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  error_message?: string | null;
  scope_id?: string | null;
}

interface GraphClaim {
  claim_id: string;
  claim_text: string;
  claim_type: string;
  source_type?: string;
  source_ref?: string;
  extracted_at?: string;
}

interface GraphDiagnostics {
  twin: {
    id: string;
    name: string;
    tenant_id: string;
    creator_id: string;
    scope_id: string;
    created_at?: string;
  };
  neo4j: {
    status: string;
    message?: string;
    database?: string | null;
    probe_ms?: number;
    total_nodes?: number;
    total_episodes?: number;
  };
  graph_config: {
    enabled: boolean;
    read_enabled: boolean;
    write_enabled: boolean;
    database?: string | null;
  };
  outbox: {
    stats: {
      pending: number;
      processing: number;
      completed: number;
      failed: number;
    };
    recent_jobs: GraphOutboxJob[];
  };
  claims: {
    count: number;
    recent: GraphClaim[];
  };
  snapshot?: {
    scope_id?: string;
    group_id?: string;
    episode_count?: number;
    claim_count?: number;
    created_at?: string;
    expires_at?: string;
    snapshot_data?: {
      summary?: string;
      topics?: string[];
    };
  } | null;
  recent_episodes: Array<{
    name?: string;
    content?: string;
  }>;
  latest_name_research_run?: {
    id: string;
    status?: string;
    input_name?: string;
    run_completed_at?: string;
    created_at?: string;
  } | null;
}

interface ActionResult {
  status: string;
  message?: string;
  seed_token?: string;
  match_count?: number;
  run_id?: string;
}

interface AdminBootstrapResponse {
  health: SystemHealth | null;
  version: VersionInfo | null;
  twins: TwinSummary[];
}

function statusFromService(text: string): HealthState {
  if (!text) return 'checking';
  const lower = text.toLowerCase();
  if (lower === 'connected' || lower === 'online') return 'healthy';
  if (lower.includes('degraded') || lower.includes('not_configured')) return 'degraded';
  if (lower.includes('error') || lower.includes('failed')) return 'unhealthy';
  return 'checking';
}

function cardTone(status: HealthState): string {
  switch (status) {
    case 'healthy':
      return 'border-emerald-200 bg-emerald-50 text-emerald-900';
    case 'degraded':
      return 'border-amber-200 bg-amber-50 text-amber-900';
    case 'unhealthy':
      return 'border-rose-200 bg-rose-50 text-rose-900';
    default:
      return 'border-slate-200 bg-white text-slate-900';
  }
}

function formatDate(value?: string): string {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function truncate(text?: string, limit = 180): string {
  const value = String(text || '').trim();
  if (!value) return 'None';
  return value.length > limit ? `${value.slice(0, limit)}...` : value;
}

export default function AdminDiagnosticsPage() {
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [twins, setTwins] = useState<TwinSummary[]>([]);
  const [selectedTwinId, setSelectedTwinId] = useState<string>('');
  const [graphDiagnostics, setGraphDiagnostics] = useState<GraphDiagnostics | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [loadingBase, setLoadingBase] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<'idle' | 'seeding' | 'replaying'>('idle');
  const [actionResult, setActionResult] = useState<ActionResult | null>(null);

  const fetchGraphDiagnostics = useCallback(
    async (twinId: string) => {
      if (!twinId) {
        setGraphDiagnostics(null);
        return;
      }

      setLoadingGraph(true);
      setError(null);
      try {
        const response = await fetch(`/api/admin/graph/${twinId}`, {
          cache: 'no-store',
        });
        if (!response.ok) {
          throw new Error(`Graph diagnostics failed with HTTP ${response.status}`);
        }
        const data: GraphDiagnostics = await response.json();
        setGraphDiagnostics(data);
      } catch (fetchError) {
        setGraphDiagnostics(null);
        setError(fetchError instanceof Error ? fetchError.message : 'Unable to load graph diagnostics.');
      } finally {
        setLoadingGraph(false);
      }
    },
    []
  );

  const fetchBaseData = useCallback(async () => {
    setLoadingBase(true);
    setError(null);
    try {
      const response = await fetch('/api/admin/bootstrap', {
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(`Admin bootstrap failed with HTTP ${response.status}`);
      }
      const bootstrap = (await response.json()) as AdminBootstrapResponse;
      setSystemHealth(bootstrap.health);
      setVersion(bootstrap.version);
      const twinRows = Array.isArray(bootstrap.twins) ? bootstrap.twins : [];
      setTwins(twinRows);
      setSelectedTwinId((current) => current || twinRows[0]?.id || '');
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Unable to load admin diagnostics.');
    } finally {
      setLoadingBase(false);
    }
  }, []);

  useEffect(() => {
    void fetchBaseData();
  }, [fetchBaseData]);

  useEffect(() => {
    if (selectedTwinId) {
      void fetchGraphDiagnostics(selectedTwinId);
    }
  }, [fetchGraphDiagnostics, selectedTwinId]);

  const triggerGraphAction = useCallback(
    async (mode: 'seed' | 'replay') => {
      if (!selectedTwinId) return;
      setActionState(mode === 'seed' ? 'seeding' : 'replaying');
      setActionResult(null);
      setError(null);
      try {
        const endpoint =
          mode === 'seed'
            ? `/api/admin/graph/${selectedTwinId}/seed`
            : `/api/admin/graph/${selectedTwinId}/replay`;

        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body:
            mode === 'seed'
              ? JSON.stringify({
                  label: `Diagnostics Seed for ${graphDiagnostics?.twin.name || selectedTwinId}`,
                })
              : JSON.stringify({}),
        });

        if (!response.ok) {
          throw new Error(`${mode} failed with HTTP ${response.status}`);
        }

        const data: ActionResult = await response.json();
        setActionResult(data);
        await fetchGraphDiagnostics(selectedTwinId);
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : 'Graph action failed.');
      } finally {
        setActionState('idle');
      }
    },
    [fetchGraphDiagnostics, graphDiagnostics?.twin.name, selectedTwinId]
  );

  const neo4jState = useMemo<HealthState>(() => {
    if (graphDiagnostics?.neo4j.status) {
      return statusFromService(graphDiagnostics.neo4j.status);
    }
    return systemHealth ? statusFromService(systemHealth.services.neo4j) : 'checking';
  }, [graphDiagnostics, systemHealth]);

  const backendState = useMemo<HealthState>(() => {
    return systemHealth ? statusFromService(systemHealth.status) : 'checking';
  }, [systemHealth]);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <div className={`rounded-2xl border p-5 ${cardTone(backendState)}`}>
          <div className="text-sm font-medium">Backend API</div>
          <div className="mt-2 text-2xl font-semibold">
            {systemHealth?.status || 'Checking'}
          </div>
          <p className="mt-2 text-sm opacity-80">
            OpenAI: {systemHealth?.services.openai || 'Unknown'} | Pinecone: {systemHealth?.services.pinecone || 'Unknown'}
          </p>
        </div>
        <div className={`rounded-2xl border p-5 ${cardTone(neo4jState)}`}>
          <div className="text-sm font-medium">Neo4j</div>
          <div className="mt-2 text-2xl font-semibold">
            {graphDiagnostics?.neo4j.status || systemHealth?.services.neo4j || 'Checking'}
          </div>
          <p className="mt-2 text-sm opacity-80">
            Database: {graphDiagnostics?.neo4j.database || graphDiagnostics?.graph_config.database || 'Unknown'}
          </p>
          <p className="mt-1 text-sm opacity-80">
            Probe: {graphDiagnostics?.neo4j.probe_ms ? `${graphDiagnostics.neo4j.probe_ms}ms` : 'Unknown'}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 text-slate-900">
          <div className="text-sm font-medium">Deployment</div>
          <div className="mt-2 text-2xl font-semibold">{version?.git_sha || 'Unknown'}</div>
          <p className="mt-2 text-sm text-slate-500">
            {version?.service || 'Service unknown'} | {version?.environment || 'Environment unknown'}
          </p>
          <p className="mt-1 text-sm text-slate-500">Built: {formatDate(version?.build_time)}</p>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Graph Diagnostics</h2>
            <p className="mt-1 text-sm text-slate-500">
              Inspect one twin at a time, verify Neo4j episode writes, and replay the latest research artifact into graph memory.
            </p>
          </div>
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <label className="flex flex-col gap-1 text-sm text-slate-600">
              Twin
              <select
                value={selectedTwinId}
                onChange={(event) => setSelectedTwinId(event.target.value)}
                className="min-w-[280px] rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
              >
                {twins.map((twin) => (
                  <option key={twin.id} value={twin.id}>
                    {twin.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              onClick={() => {
                void fetchBaseData();
                if (selectedTwinId) {
                  void fetchGraphDiagnostics(selectedTwinId);
                }
              }}
              className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
            <button
              onClick={() => void triggerGraphAction('seed')}
              disabled={!selectedTwinId || actionState !== 'idle'}
              className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {actionState === 'seeding' ? 'Seeding...' : 'Seed Test Episode'}
            </button>
            <button
              onClick={() => void triggerGraphAction('replay')}
              disabled={!selectedTwinId || actionState !== 'idle'}
              className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {actionState === 'replaying' ? 'Replaying...' : 'Replay Latest Research'}
            </button>
          </div>
        </div>

        {actionResult && (
          <div className="mt-4 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
            <div className="font-medium">Latest action</div>
            <div className="mt-1">
              {actionResult.message || `Status: ${actionResult.status}`}
            </div>
            {actionResult.seed_token && (
              <div className="mt-1">Seed token: {actionResult.seed_token}</div>
            )}
            {typeof actionResult.match_count === 'number' && (
              <div className="mt-1">Matched results: {actionResult.match_count}</div>
            )}
            {actionResult.run_id && <div className="mt-1">Run ID: {actionResult.run_id}</div>}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
            {error}
          </div>
        )}

        {loadingBase || loadingGraph ? (
          <div className="mt-8 text-sm text-slate-500">Loading diagnostics...</div>
        ) : graphDiagnostics ? (
          <div className="mt-8 space-y-6">
            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Scope</div>
                <div className="mt-2 break-all text-sm font-medium text-slate-900">{graphDiagnostics.twin.scope_id}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Outbox Pending</div>
                <div className="mt-2 text-3xl font-semibold text-slate-900">{graphDiagnostics.outbox.stats.pending}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Claims</div>
                <div className="mt-2 text-3xl font-semibold text-slate-900">{graphDiagnostics.claims.count}</div>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Snapshot Episodes</div>
                <div className="mt-2 text-3xl font-semibold text-slate-900">
                  {graphDiagnostics.snapshot?.episode_count ?? 0}
                </div>
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 p-5">
                <h3 className="text-base font-semibold text-slate-900">Recent Neo4j Episodes</h3>
                <div className="mt-4 space-y-3">
                  {graphDiagnostics.recent_episodes.length > 0 ? (
                    graphDiagnostics.recent_episodes.map((episode, index) => (
                      <div key={`${episode.name || 'episode'}-${index}`} className="rounded-xl bg-slate-50 p-3">
                        <div className="text-sm font-medium text-slate-900">{episode.name || 'Episode'}</div>
                        <div className="mt-1 text-sm text-slate-600">{truncate(episode.content, 220)}</div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-slate-500">No Neo4j episodes found for this scope.</div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 p-5">
                <h3 className="text-base font-semibold text-slate-900">Snapshot</h3>
                {graphDiagnostics.snapshot ? (
                  <div className="mt-4 space-y-3 text-sm text-slate-600">
                    <div>Created: {formatDate(graphDiagnostics.snapshot.created_at)}</div>
                    <div>Expires: {formatDate(graphDiagnostics.snapshot.expires_at)}</div>
                    <div>Claims: {graphDiagnostics.snapshot.claim_count ?? 0}</div>
                    <div>Episodes: {graphDiagnostics.snapshot.episode_count ?? 0}</div>
                    <div>
                      Summary: {truncate(graphDiagnostics.snapshot.snapshot_data?.summary, 220)}
                    </div>
                    <div>
                      Topics:{' '}
                      {(graphDiagnostics.snapshot.snapshot_data?.topics || []).length > 0
                        ? graphDiagnostics.snapshot.snapshot_data?.topics?.join(', ')
                        : 'None'}
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 text-sm text-slate-500">No graph snapshot found for this twin.</div>
                )}
              </div>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 p-5">
                <h3 className="text-base font-semibold text-slate-900">Recent Outbox Jobs</h3>
                <div className="mt-4 space-y-3">
                  {graphDiagnostics.outbox.recent_jobs.length > 0 ? (
                    graphDiagnostics.outbox.recent_jobs.map((job) => (
                      <div key={job.id} className="rounded-xl bg-slate-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-medium text-slate-900">{job.operation}</div>
                          <div className="rounded-full bg-white px-2 py-1 text-xs font-medium text-slate-700">
                            {job.status}
                          </div>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">Created: {formatDate(job.created_at)}</div>
                        {job.error_message && (
                          <div className="mt-2 text-xs text-rose-700">{truncate(job.error_message, 180)}</div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-slate-500">No graph outbox jobs recorded for this scope.</div>
                  )}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 p-5">
                <h3 className="text-base font-semibold text-slate-900">Recent Claims</h3>
                <div className="mt-4 space-y-3">
                  {graphDiagnostics.claims.recent.length > 0 ? (
                    graphDiagnostics.claims.recent.map((claim) => (
                      <div key={claim.claim_id} className="rounded-xl bg-slate-50 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-medium text-slate-900">{claim.claim_type}</div>
                          <div className="text-xs text-slate-500">
                            {claim.source_type || 'Source type unknown'}
                          </div>
                        </div>
                        <div className="mt-1 text-sm text-slate-600">{truncate(claim.claim_text, 220)}</div>
                        <div className="mt-1 text-xs text-slate-500">Extracted: {formatDate(claim.extracted_at)}</div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-slate-500">No graph claims stored for this scope.</div>
                  )}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 p-5">
              <h3 className="text-base font-semibold text-slate-900">Latest Name Research Run</h3>
              {graphDiagnostics.latest_name_research_run ? (
                <div className="mt-4 grid gap-3 md:grid-cols-2 text-sm text-slate-600">
                  <div>Run ID: {graphDiagnostics.latest_name_research_run.id}</div>
                  <div>Status: {graphDiagnostics.latest_name_research_run.status || 'Unknown'}</div>
                  <div>Input name: {graphDiagnostics.latest_name_research_run.input_name || 'Unknown'}</div>
                  <div>
                    Completed: {formatDate(graphDiagnostics.latest_name_research_run.run_completed_at)}
                  </div>
                </div>
              ) : (
                <div className="mt-4 text-sm text-slate-500">No name deep research run found for this twin.</div>
              )}
            </div>
          </div>
        ) : (
          <div className="mt-8 text-sm text-slate-500">No graph diagnostics available yet.</div>
        )}
      </section>
    </div>
  );
}
