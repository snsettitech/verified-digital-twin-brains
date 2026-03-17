/**
 * ClaimsReview Component (Phase 8)
 * 
 * Displays claim enrichment progress and allows manual review of claims.
 * Integrated into the research flow after completion.
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import {
  researchClaimsApi,
  ResearchClaim,
  ClaimsStatusResponse,
  VerificationStatus,
  getVerificationStatusLabel,
  getVerificationStatusColor,
  getClaimTypeLabel,
  isEnrichmentTerminal,
} from '@/lib/api/researchClaims';

interface ClaimsReviewProps {
  twinId: string;
  researchRunId: string;
  onComplete: () => void;
  onSkip: () => void;
}

export function ClaimsReview({
  twinId,
  researchRunId,
  onComplete,
  onSkip,
}: ClaimsReviewProps) {
  const [status, setStatus] = useState<ClaimsStatusResponse | null>(null);
  const [claims, setClaims] = useState<ResearchClaim[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<VerificationStatus | 'all'>('all');
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  // Load enrichment status and start if needed
  const loadStatus = useCallback(async () => {
    try {
      const currentStatus = await researchClaimsApi.getClaimsStatus(twinId, researchRunId);
      setStatus(currentStatus);

      // If not started or not terminal, trigger enrichment
      if (currentStatus.status === 'not_started' || currentStatus.status === 'pending') {
        setIsProcessing(true);
        const result = await researchClaimsApi.continueClaims(twinId, researchRunId);
        
        // Update status after starting
        const updatedStatus = await researchClaimsApi.getClaimsStatus(twinId, researchRunId);
        setStatus(updatedStatus);
        setIsProcessing(false);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load claims status';
      setError(msg);
      setIsProcessing(false);
    }
  }, [twinId, researchRunId]);

  // Load claims
  const loadClaims = useCallback(async () => {
    try {
      const options = activeFilter !== 'all' 
        ? { verificationStatus: activeFilter, limit: 100 }
        : { limit: 100 };
      
      const result = await researchClaimsApi.listClaims(twinId, researchRunId, options);
      setClaims(result.items);
    } catch (err) {
      console.error('Failed to load claims:', err);
    }
  }, [twinId, researchRunId, activeFilter]);

  // Initial load
  useEffect(() => {
    loadStatus().then(() => setIsLoading(false));
  }, [loadStatus]);

  // Poll for completion and load claims when enriching
  useEffect(() => {
    if (!status || isEnrichmentTerminal(status.status)) {
      loadClaims();
      return;
    }

    // Poll every 3 seconds while enriching
    const interval = setInterval(() => {
      loadStatus().then(() => {
        if (status && isEnrichmentTerminal(status.status)) {
          loadClaims();
        }
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [status?.status, loadStatus, loadClaims]);

  // Handle claim resolution
  const handleResolve = async (claimId: string, newStatus: VerificationStatus) => {
    setResolvingId(claimId);
    try {
      await researchClaimsApi.resolveClaim(twinId, researchRunId, claimId, {
        status: newStatus,
      });
      // Reload claims
      await loadClaims();
      await loadStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to resolve claim';
      setError(msg);
    } finally {
      setResolvingId(null);
    }
  };

  // Status badge component
  const StatusBadge = ({ status }: { status: VerificationStatus }) => {
    const color = getVerificationStatusColor(status);
    const colorClasses = {
      green: 'bg-green-500/20 text-green-400 border-green-500/30',
      yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      red: 'bg-red-500/20 text-red-400 border-red-500/30',
      gray: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    };

    return (
      <span className={`px-2 py-1 text-xs rounded border ${colorClasses[color]}`}>
        {getVerificationStatusLabel(status)}
      </span>
    );
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Loading Claims</h2>
          <p className="text-slate-400">Checking claim enrichment status...</p>
        </div>
        <Card className="p-12 bg-slate-900 border-slate-700 text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Loading...</p>
        </Card>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Error</h2>
          <p className="text-slate-400">Failed to load claims</p>
        </div>
        <Card className="p-6 bg-red-500/10 border-red-500/30">
          <p className="text-red-400">{error}</p>
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => { setError(null); loadStatus(); }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg"
            >
              Retry
            </button>
            <button
              onClick={onSkip}
              className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg"
            >
              Skip
            </button>
          </div>
        </Card>
      </div>
    );
  }

  // Processing/enriching state
  if (status?.status === 'enriching' || isProcessing) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Extracting Claims</h2>
          <p className="text-slate-400">Analyzing your sources for factual claims...</p>
        </div>
        <Card className="p-12 bg-slate-900 border-slate-700 text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Extracting and verifying claims...</p>
          <p className="text-sm text-slate-500 mt-2">This may take a minute</p>
        </Card>
      </div>
    );
  }

  // Failed state
  if (status?.status === 'failed') {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Claims Extraction Failed</h2>
          <p className="text-slate-400">Could not extract claims from sources</p>
        </div>
        <Card className="p-6 bg-red-500/10 border-red-500/30">
          <p className="text-red-400">{status.error_message || 'Unknown error'}</p>
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => { setError(null); loadStatus(); }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg"
            >
              Retry
            </button>
            <button
              onClick={onSkip}
              className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg"
            >
              Skip
            </button>
          </div>
        </Card>
      </div>
    );
  }

  // Main claims review UI
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">
          Review Extracted Claims
        </h2>
        <p className="text-slate-400">
          We found {status?.total_claims || 0} claims in your sources. Review and verify them.
        </p>
      </div>

      {/* Summary Stats */}
      {status && (
        <div className="grid grid-cols-5 gap-3">
          <div className="bg-slate-800 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-white">{status.total_claims}</div>
            <div className="text-xs text-slate-400">Total</div>
          </div>
          <div className="bg-green-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-400">{status.supported_count}</div>
            <div className="text-xs text-slate-400">Supported</div>
          </div>
          <div className="bg-yellow-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-yellow-400">{status.needs_review_count}</div>
            <div className="text-xs text-slate-400">Needs Review</div>
          </div>
          <div className="bg-slate-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-slate-400">{status.insufficient_count}</div>
            <div className="text-xs text-slate-400">Insufficient</div>
          </div>
          <div className="bg-red-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-red-400">{status.conflicting_count}</div>
            <div className="text-xs text-slate-400">Conflicting</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {(['all', 'supported', 'needs_review', 'insufficient_evidence', 'conflicting'] as const).map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              activeFilter === filter
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            {filter === 'all' ? 'All' : getVerificationStatusLabel(filter)}
          </button>
        ))}
      </div>

      {/* Claims List */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {claims.length === 0 ? (
          <Card className="p-8 bg-slate-900 border-slate-700 text-center">
            <p className="text-slate-400">No claims found with the selected filter.</p>
          </Card>
        ) : (
          claims.map((claim) => (
            <Card
              key={claim.id}
              className="p-4 bg-slate-900 border-slate-700"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={claim.verification_status} />
                    <span className="text-xs text-slate-500">
                      {getClaimTypeLabel(claim.claim_type)}
                    </span>
                    <span className="text-xs text-slate-600">
                      {(claim.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  
                  <p className="text-white mb-2">{claim.claim_text}</p>
                  
                  {claim.evidence_quotes.length > 0 && (
                    <div className="mt-3 p-3 bg-slate-800/50 rounded-lg">
                      <p className="text-xs text-slate-500 mb-1">Evidence:</p>
                      <blockquote className="text-sm text-slate-400 italic border-l-2 border-slate-600 pl-3">
                        &ldquo;{claim.evidence_quotes[0].quote.substring(0, 150)}...&rdquo;
                      </blockquote>
                      {claim.source_url && (
                        <a
                          href={claim.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-400 hover:text-blue-300 mt-1 block"
                        >
                          Source →
                        </a>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions for needs_review or pending */}
                {(claim.verification_status === 'needs_review' || claim.verification_status === 'pending') && (
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => handleResolve(claim.id, 'supported')}
                      disabled={resolvingId === claim.id}
                      className="px-3 py-1.5 text-sm bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded transition-colors disabled:opacity-50"
                    >
                      {resolvingId === claim.id ? '...' : '✓ Confirm'}
                    </button>
                    <button
                      onClick={() => handleResolve(claim.id, 'insufficient_evidence')}
                      disabled={resolvingId === claim.id}
                      className="px-3 py-1.5 text-sm bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded transition-colors disabled:opacity-50"
                    >
                      ✕ Reject
                    </button>
                  </div>
                )}
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-between pt-4 border-t border-slate-800">
        <button
          onClick={onSkip}
          className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
        >
          Skip Review
        </button>
        <button
          onClick={onComplete}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors"
        >
          Continue →
        </button>
      </div>
    </div>
  );
}

export default ClaimsReview;
