import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { resolveApiBaseUrl } from '@/lib/api';

export type NameDeepResearchStatus =
  | 'created'
  | 'searching'
  | 'crawling'
  | 'extracting'
  | 'synthesizing'
  | 'completed'
  | 'failed';

export interface NameDeepResearchHints {
  location?: string | null;
  company?: string | null;
  website?: string | null;
}

export interface CreateNameDeepResearchRunRequest {
  name: string;
  hints: NameDeepResearchHints;
  idempotency_key?: string;
}

export interface CreateNameDeepResearchRunResponse {
  run_id: string;
  status: NameDeepResearchStatus;
  created_at: string;
  run_started_at?: string;
}

export interface NameDeepResearchRunStatusResponse {
  run_id: string;
  status: NameDeepResearchStatus;
  input: {
    name: string;
    hints: NameDeepResearchHints;
  };
  crawl_stats: {
    queries_used: string[];
    urls_considered: number;
    urls_crawled: number;
    urls_blocked: number;
    sources_used_in_final: number;
    words_extracted: number;
    run_started_at?: string;
    run_completed_at?: string;
  };
  selected_model?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  run_started_at?: string;
  run_completed_at?: string;
}

const BASE_URL = resolveApiBaseUrl();

async function readError(response: Response): Promise<Error> {
  const payload = await response.json().catch(() => null) as { message?: string; detail?: { message?: string } } | null;
  const msg = payload?.detail?.message || payload?.message || `Request failed with status ${response.status}`;
  return new Error(msg);
}

export const nameDeepResearchApi = {
  async createRun(
    request: CreateNameDeepResearchRunRequest
  ): Promise<CreateNameDeepResearchRunResponse> {
    const response = await authFetchStandalone(`${BASE_URL}/deep-research/runs`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
    if (!response.ok) throw await readError(response);
    return response.json();
  },

  async getRun(runId: string): Promise<NameDeepResearchRunStatusResponse> {
    const response = await authFetchStandalone(`${BASE_URL}/deep-research/runs/${runId}`);
    if (!response.ok) throw await readError(response);
    return response.json();
  },

  async downloadResult(runId: string): Promise<Record<string, unknown>> {
    const response = await authFetchStandalone(`${BASE_URL}/deep-research/runs/${runId}/result.json`);
    if (!response.ok) throw await readError(response);
    return response.json();
  },
};
