/**
 * Research Claims API Client (Phase 8)
 * 
 * API client for claim enrichment workflow.
 * All changes are additive and backward compatible.
 */

import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { resolveApiBaseUrl } from '@/lib/api';

// =============================================================================
// Types (aligned with backend contracts)
// =============================================================================

export type ClaimType = 
  | 'preference'
  | 'belief'
  | 'heuristic'
  | 'value'
  | 'experience'
  | 'boundary'
  | 'uncertain';

export type VerificationStatus = 
  | 'pending'
  | 'supported'
  | 'insufficient_evidence'
  | 'conflicting'
  | 'needs_review';

export type EnrichmentStatus = 
  | 'not_started'
  | 'pending'
  | 'enriching'
  | 'completed'
  | 'failed';

export interface ClaimEvidenceItem {
  quote: string;
  source_id?: string;
  source_url?: string;
  relevance: number;
}

export interface ResearchClaim {
  id: string;
  claim_text: string;
  claim_type: ClaimType;
  verification_status: VerificationStatus;
  authority: string;
  source_id?: string;
  source_url?: string;
  source_title?: string;
  evidence_quotes: ClaimEvidenceItem[];
  created_at: string;
  reviewed_at?: string;
  review_notes?: string;
}

export interface ContinueClaimsResponse {
  research_run_id: string;
  twin_id: string;
  status: string;
  total_claims: number;
  supported_count: number;
  insufficient_count: number;
  conflicting_count: number;
  needs_review_count: number;
  message: string;
}

export interface ClaimsStatusResponse {
  research_run_id: string;
  twin_id: string;
  status: EnrichmentStatus;
  total_claims: number;
  supported_count: number;
  insufficient_count: number;
  conflicting_count: number;
  needs_review_count: number;
  pending_count: number;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface ClaimsListResponse {
  items: ResearchClaim[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ResolveClaimRequest {
  status: VerificationStatus;
  notes?: string;
}

export interface ResolveClaimResponse {
  claim_id: string;
  research_run_id: string;
  previous_status: string;
  new_status: string;
  resolved_at: string;
  message: string;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get human-readable label for verification status
 */
export function getVerificationStatusLabel(status: VerificationStatus): string {
  const labels: Record<VerificationStatus, string> = {
    pending: 'Pending',
    supported: 'Supported',
    insufficient_evidence: 'Insufficient Evidence',
    conflicting: 'Conflicting',
    needs_review: 'Needs Review',
  };
  return labels[status] || status;
}

/**
 * Get color for verification status badge
 */
export function getVerificationStatusColor(status: VerificationStatus): 'green' | 'yellow' | 'red' | 'gray' {
  const colors: Record<VerificationStatus, 'green' | 'yellow' | 'red' | 'gray'> = {
    pending: 'gray',
    supported: 'green',
    insufficient_evidence: 'yellow',
    conflicting: 'red',
    needs_review: 'yellow',
  };
  return colors[status] || 'gray';
}

/**
 * Get human-readable label for claim type
 */
export function getClaimTypeLabel(type: ClaimType): string {
  const labels: Record<ClaimType, string> = {
    preference: 'Preference',
    belief: 'Belief',
    heuristic: 'Heuristic',
    value: 'Value',
    experience: 'Experience',
    boundary: 'Boundary',
    uncertain: 'Uncertain',
  };
  return labels[type] || type;
}

/**
 * Check if enrichment is in a terminal state
 */
export function isEnrichmentTerminal(status: EnrichmentStatus): boolean {
  return status === 'completed' || status === 'failed';
}

// =============================================================================
// API Client
// =============================================================================

const BASE_URL = resolveApiBaseUrl();

export const researchClaimsApi = {
  /**
   * Start or continue claim enrichment
   * POST /twins/{twin_id}/research/{research_run_id}/continue-claims
   */
  async continueClaims(
    twinId: string,
    researchRunId: string
  ): Promise<ContinueClaimsResponse> {
    const response = await authFetchStandalone(
      `${BASE_URL}/twins/${twinId}/research/${researchRunId}/continue-claims`,
      {
        method: 'POST',
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `Failed to start claim enrichment: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Get enrichment status
   * GET /twins/{twin_id}/research/{research_run_id}/claims-status
   */
  async getClaimsStatus(
    twinId: string,
    researchRunId: string
  ): Promise<ClaimsStatusResponse> {
    const response = await authFetchStandalone(
      `${BASE_URL}/twins/${twinId}/research/${researchRunId}/claims-status`
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `Failed to get claims status: ${response.status}`);
    }

    return response.json();
  },

  /**
   * List claims with optional filters
   * GET /twins/{twin_id}/research/{research_run_id}/claims
   */
  async listClaims(
    twinId: string,
    researchRunId: string,
    options?: {
      verificationStatus?: VerificationStatus;
      claimType?: ClaimType;
      limit?: number;
      offset?: number;
    }
  ): Promise<ClaimsListResponse> {
    const params = new URLSearchParams();
    if (options?.verificationStatus) params.set('verification_status', options.verificationStatus);
    if (options?.claimType) params.set('claim_type', options.claimType);
    if (options?.limit) params.set('limit', String(options.limit));
    if (options?.offset) params.set('offset', String(options.offset));

    const queryString = params.toString();
    const url = `${BASE_URL}/twins/${twinId}/research/${researchRunId}/claims${queryString ? `?${queryString}` : ''}`;

    const response = await authFetchStandalone(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `Failed to list claims: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Resolve a claim's verification status
   * POST /twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/resolve
   */
  async resolveClaim(
    twinId: string,
    researchRunId: string,
    claimId: string,
    request: ResolveClaimRequest
  ): Promise<ResolveClaimResponse> {
    const response = await authFetchStandalone(
      `${BASE_URL}/twins/${twinId}/research/${researchRunId}/claims/${claimId}/resolve`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `Failed to resolve claim: ${response.status}`);
    }

    return response.json();
  },
};

export default researchClaimsApi;
