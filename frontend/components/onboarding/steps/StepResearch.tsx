/**
 * StepResearch Component (Phase 7)
 * 
 * Integrated research flow step that handles:
 * - Creating research run
 * - Polling status updates
 * - Showing confirmation UI when needed
 * - Auto-advancing through phases
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/Card';
import { 
  researchApi, 
  ResearchRunStatus,
  PendingConfirmationItem,
  CreateResearchRunRequest,
} from '@/lib/api/research';
import { useResearchPoller } from '@/lib/hooks/useResearchPoller';
import { ResearchProgress } from '@/components/onboarding/ResearchProgress';
import { ResearchConfirmation } from '@/components/onboarding/ResearchConfirmation';
import { ClaimsReview } from '@/components/onboarding/ClaimsReview';

interface StepResearchProps {
  twinId: string | null;
  claimedIdentity: {
    fullName: string;
    location?: string;
    role?: string;
    headline?: string;
    preferredTwinName?: string;
  };
  /** URLs to crawl; optional when fullName provided (Firecrawl search used) */
  seedUrls?: string[];
  onComplete: (researchRunId?: string) => void;
  onBack: () => void;
}

export function StepResearch({
  twinId,
  claimedIdentity,
  seedUrls,
  onComplete,
  onBack,
}: StepResearchProps) {
  const router = useRouter();
  
  // Research run state
  const [researchRunId, setResearchRunId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  
  // Confirmation state
  const [pendingConfirmations, setPendingConfirmations] = useState<PendingConfirmationItem[]>([]);
  const [isLoadingConfirmations, setIsLoadingConfirmations] = useState(false);
  
  // Continue action state
  const [isContinuing, setIsContinuing] = useState(false);
  
  // Polling hook
  const {
    status,
    isPolling,
    error: pollingError,
    isTerminal,
    isCompleted,
    startPolling,
    stopPolling,
    refresh,
    retry: retryPolling,
  } = useResearchPoller({
    twinId,
    researchRunId: null,
    debug: false,
  });

  // Create research run on mount
  useEffect(() => {
    if (twinId && !researchRunId && !isCreating) {
      createResearchRun();
    }
    
    return () => {
      stopPolling();
    };
  }, [twinId]);

  // Handle status changes
  useEffect(() => {
    if (!status) return;

    // Load confirmations when awaiting_confirmation
    if (status.status === 'awaiting_confirmation') {
      loadPendingConfirmations();
    }

    // Auto-advance through phases
    if (status.status === 'ready_for_ingestion') {
      handleContinueIngestion();
    } else if (status.status === 'ingestion_completed') {
      handleContinueBio();
    } else if (status.status === 'bio_generated') {
      handleContinueFinalize();
    }
    // status === 'completed': ClaimsReview is shown; user completes via that
  }, [status?.status]);

  // Create research run
  const createResearchRun = async () => {
    if (!twinId) return;
    
    setIsCreating(true);
    setCreateError(null);

    try {
      const urls = seedUrls ?? [];
      const request: CreateResearchRunRequest = {
        claimed_identity: {
          full_name: claimedIdentity.fullName,
          location: claimedIdentity.location,
          submitted_links: urls,
          role: claimedIdentity.role,
          headline: claimedIdentity.headline,
          preferred_twin_name: claimedIdentity.preferredTwinName,
        },
        seed_urls: urls,
      };

      const response = await researchApi.createResearchRun(twinId, request);
      setResearchRunId(response.research_run_id);
      
      // Start polling for status
      startPolling(twinId, response.research_run_id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start research';
      setCreateError(msg);
      console.error('Create research error:', err);
    } finally {
      setIsCreating(false);
    }
  };

  // Load pending confirmations
  const loadPendingConfirmations = async () => {
    if (!twinId || !researchRunId) return;
    
    setIsLoadingConfirmations(true);
    try {
      const response = await researchApi.getPendingConfirmations(twinId, researchRunId, {
        limit: 100,
      });
      setPendingConfirmations(response.items);
    } catch (err) {
      console.error('Load confirmations error:', err);
    } finally {
      setIsLoadingConfirmations(false);
    }
  };

  // Handle continue to ingestion
  const handleContinueIngestion = async () => {
    if (!twinId || !researchRunId || isContinuing) return;
    
    setIsContinuing(true);
    try {
      await researchApi.continueIngestion(twinId, researchRunId);
      await refresh();
    } catch (err) {
      console.error('Continue ingestion error:', err);
    } finally {
      setIsContinuing(false);
    }
  };

  // Handle continue to bio generation
  const handleContinueBio = async () => {
    if (!twinId || !researchRunId || isContinuing) return;
    
    setIsContinuing(true);
    try {
      await researchApi.continueBio(twinId, researchRunId);
      await refresh();
    } catch (err) {
      console.error('Continue bio error:', err);
    } finally {
      setIsContinuing(false);
    }
  };

  // Handle continue to finalization
  const handleContinueFinalize = async () => {
    if (!twinId || !researchRunId || isContinuing) return;
    
    setIsContinuing(true);
    try {
      await researchApi.continueFinalize(twinId, researchRunId);
      await refresh();
    } catch (err) {
      console.error('Continue finalize error:', err);
    } finally {
      setIsContinuing(false);
    }
  };

  // Handle confirmations updated
  const handleConfirmationsUpdated = async () => {
    await loadPendingConfirmations();
    await refresh();
  };

  // Handle retry after error
  const handleRetry = () => {
    if (createError) {
      createResearchRun();
    } else {
      retryPolling();
    }
  };

  // Get summary for completed state
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof researchApi.getResearchSummary>> | null>(null);
  
  useEffect(() => {
    if (isCompleted && twinId) {
      researchApi.getResearchSummary(twinId).then(setSummary).catch(console.error);
    }
  }, [isCompleted, twinId]);
  
  // Phase 8: Claims enrichment state
  const [showClaimsReview, setShowClaimsReview] = useState(false);
  
  // Handle completion of research - show claims review
  useEffect(() => {
    if (status?.status === 'completed' && !showClaimsReview) {
      // Give user a moment to see completion, then show claims
      const timer = setTimeout(() => {
        setShowClaimsReview(true);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [status?.status, showClaimsReview]);

  // Loading state while creating research run
  if (isCreating) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Starting Research</h2>
          <p className="text-slate-400">Initializing your persona build...</p>
        </div>
        <Card className="p-12 bg-slate-900 border-slate-700 text-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-400">Creating research run...</p>
        </Card>
      </div>
    );
  }

  // Error state
  if (createError) {
    return (
      <div className="space-y-6">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Error</h2>
          <p className="text-slate-400">Failed to start research</p>
        </div>
        <Card className="p-6 bg-red-500/10 border-red-500/30">
          <p className="text-red-400">{createError}</p>
          <div className="flex gap-3 mt-4">
            <button
              onClick={onBack}
              className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-800"
            >
              Go Back
            </button>
            <button
              onClick={handleRetry}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg"
            >
              Try Again
            </button>
          </div>
        </Card>
      </div>
    );
  }

  // Confirmation state
  if (status?.status === 'awaiting_confirmation') {
    return (
      <div className="space-y-6">
        <ResearchConfirmation
          twinId={twinId!}
          researchRunId={researchRunId!}
          pendingConfirmations={pendingConfirmations}
          confirmationSummary={status.confirmation_summary}
          onConfirmationsUpdated={handleConfirmationsUpdated}
          onContinue={handleContinueIngestion}
        />
        
        {/* Manual continue button if no pending confirmations */}
        {pendingConfirmations.length === 0 && (
          <button
            onClick={handleContinueIngestion}
            disabled={isContinuing}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors"
          >
            {isContinuing ? 'Continuing...' : 'Continue to Ingestion'}
          </button>
        )}
      </div>
    );
  }

  // Phase 8: Claims review state
  if (showClaimsReview && researchRunId) {
    return (
      <ClaimsReview
        twinId={twinId!}
        researchRunId={researchRunId}
        onComplete={() => onComplete(researchRunId)}
        onSkip={() => onComplete(researchRunId)}
      />
    );
  }

  // Progress state (all other statuses)
  return (
    <div className="space-y-6">
      <ResearchProgress
        status={status}
        summary={summary}
        isPolling={isPolling}
        error={pollingError}
        onRetry={handleRetry}
        onContinueIngestion={handleContinueIngestion}
        onContinueBio={handleContinueBio}
        onContinueFinalize={handleContinueFinalize}
        isContinuing={isContinuing}
      />
      
      {/* Back button for non-terminal states */}
      {!isTerminal && (
        <div className="flex justify-start">
          <button
            onClick={onBack}
            className="px-4 py-2 text-slate-400 hover:text-white transition-colors"
          >
            ← Back
          </button>
        </div>
      )}
    </div>
  );
}

export default StepResearch;
