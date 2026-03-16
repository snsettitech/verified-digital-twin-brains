/**
 * ResearchProgress Component (Phase 7)
 * 
 * Displays research run status with progress indicators, status badges,
 * and action buttons for each phase.
 */

'use client';

import { Card } from '@/components/ui/Card';
import {
  ResearchRunStatus,
  ResearchRunStatusResponse,
  ResearchSummaryResponse,
  getStatusLabel,
  isTerminalStatus,
} from '@/lib/api/research';

interface ResearchProgressProps {
  status: ResearchRunStatusResponse | null;
  summary?: ResearchSummaryResponse | null;
  isPolling: boolean;
  error: string | null;
  onRetry: () => void;
  onContinueIngestion: () => Promise<void>;
  onContinueBio: () => Promise<void>;
  onContinueFinalize: () => Promise<void>;
  isContinuing: boolean;
}

export function ResearchProgress({
  status,
  summary,
  isPolling,
  error,
  onRetry,
  onContinueIngestion,
  onContinueBio,
  onContinueFinalize,
  isContinuing,
}: ResearchProgressProps) {
  const currentStatus = status?.status;
  const warningList = Array.isArray(status?.checkpoint_data?.warnings)
    ? status.checkpoint_data.warnings
    : [];
  const ingestionErrors = Array.isArray(status?.checkpoint_data?.ingestion?.errors)
    ? status.checkpoint_data.ingestion.errors
    : [];
  const failureReason =
    warningList[warningList.length - 1] ||
    ingestionErrors[0] ||
    null;
  
  // Status badge colors
  const getStatusColor = (status: ResearchRunStatus) => {
    const colors: Record<ResearchRunStatus, string> = {
      planning: 'bg-slate-500/20 text-slate-400',
      queued: 'bg-slate-500/20 text-slate-400',
      crawling: 'bg-blue-500/20 text-blue-400',
      awaiting_confirmation: 'bg-amber-500/20 text-amber-400',
      ready_for_ingestion: 'bg-green-500/20 text-green-400',
      ingesting: 'bg-blue-500/20 text-blue-400',
      ingestion_completed: 'bg-green-500/20 text-green-400',
      generating_bio: 'bg-purple-500/20 text-purple-400',
      bio_generated: 'bg-green-500/20 text-green-400',
      finalizing: 'bg-indigo-500/20 text-indigo-400',
      completed: 'bg-green-500/20 text-green-400',
      failed: 'bg-red-500/20 text-red-400',
      timed_out: 'bg-orange-500/20 text-orange-400',
    };
    return colors[status] || 'bg-slate-500/20 text-slate-400';
  };

  // Progress steps
  const steps = [
    { key: 'crawling', label: 'Crawling', statuses: ['planning', 'queued', 'crawling'] },
    { key: 'confirmation', label: 'Confirmation', statuses: ['awaiting_confirmation'] },
    { key: 'ingestion', label: 'Ingestion', statuses: ['ready_for_ingestion', 'ingesting', 'ingestion_completed'] },
    { key: 'bio', label: 'Bio Generation', statuses: ['generating_bio', 'bio_generated'] },
    { key: 'finalizing', label: 'Finalizing', statuses: ['finalizing', 'completed'] },
  ];

  // Get current step index
  const getCurrentStepIndex = () => {
    if (!currentStatus) return -1;
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].statuses.includes(currentStatus)) return i;
    }
    return -1;
  };

  const currentStepIndex = getCurrentStepIndex();
  const crawlProgress = status?.checkpoint_data?.crawl_progress;

  // Get next action display
  const nextActions = status?.next_actions ?? [];
  const hasNextAction = nextActions.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">
          Building Your Persona
        </h2>
        <p className="text-slate-400">
          We&apos;re processing your sources and creating your personalized AI.
        </p>
        <p className="text-xs text-slate-500 mt-1">
          Usually takes around 10 minutes for first-time setup.
        </p>
      </div>

      {/* Live Metrics */}
      {status?.checkpoint_data?.ingestion && !isTerminalStatus(currentStatus || 'planning') && (
        <Card className="p-4 bg-slate-900/50 border-slate-700">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Progress</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <div className="text-lg font-semibold text-white">
                {status.checkpoint_data.ingestion.pages_ingested ?? status.checkpoint_data.ingestion.sources_ingested ?? 0}
              </div>
              <div className="text-slate-500">Pages ingested</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-white">
                {status.checkpoint_data.ingestion.chunks_created ?? 0}
              </div>
              <div className="text-slate-500">Chunks created</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-white">
                {(status.checkpoint_data.ingestion.words_processed ?? 0).toLocaleString()}
              </div>
              <div className="text-slate-500">Words ingested</div>
            </div>
            <div>
              <div className="text-lg font-semibold text-white">
                {status.checkpoint_data.ingestion.questions_answerable_estimate ?? 0}
              </div>
              <div className="text-slate-500">Est. answerable questions</div>
            </div>
          </div>
        </Card>
      )}

      {/* Status Badge */}
      {currentStatus && (
        <div className="flex justify-center">
          <span className={`px-4 py-2 rounded-full text-sm font-medium ${getStatusColor(currentStatus)}`}>
            {isPolling && !isTerminalStatus(currentStatus) && (
              <span className="inline-block w-2 h-2 bg-current rounded-full animate-pulse mr-2" />
            )}
            {getStatusLabel(currentStatus)}
          </span>
        </div>
      )}

      {/* Progress Steps */}
      <div className="relative">
        <div className="flex justify-between items-center">
          {steps.map((step, index) => {
            const isActive = index === currentStepIndex;
            const isCompleted = index < currentStepIndex;
            const isPending = index > currentStepIndex;

            return (
              <div key={step.key} className="flex-1 flex flex-col items-center">
                {/* Step Circle */}
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                    isCompleted
                      ? 'bg-green-500 text-white'
                      : isActive
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-800 text-slate-500'
                  }`}
                >
                  {isCompleted ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </div>
                
                {/* Step Label */}
                <span
                  className={`mt-2 text-xs ${
                    isActive ? 'text-white font-medium' : isCompleted ? 'text-slate-300' : 'text-slate-500'
                  }`}
                >
                  {step.label}
                </span>

                {/* Connector Line */}
                {index < steps.length - 1 && (
                  <div
                    className={`absolute top-5 h-0.5 w-[calc(20%-2.5rem)] left-[calc(${index * 20}%+${(index + 1) * 10}px)] ${
                      isCompleted ? 'bg-green-500' : 'bg-slate-700'
                    }`}
                    style={{
                      left: `calc(${index * 20}% + ${(index + 1) * 2}rem)`,
                      width: `calc(20% - 2rem)`,
                    }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="p-4 bg-red-500/10 border-red-500/30">
          <div className="flex items-start gap-3">
            <span className="text-red-400 text-xl">⚠️</span>
            <div className="flex-1">
              <h4 className="font-medium text-red-400">Error</h4>
              <p className="text-red-400/80 text-sm mt-1">{error}</p>
              <button
                onClick={onRetry}
                className="mt-3 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 text-sm rounded transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Phase-Specific Content */}
      {currentStatus === 'crawling' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <div>
              <h3 className="font-medium text-white">Crawling Your Sources</h3>
              <p className="text-sm text-slate-400">
                We&apos;re visiting the URLs you provided to gather content.
              </p>
            </div>
          </div>
          {crawlProgress && (
            <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <div className="text-lg font-semibold text-white">
                  {crawlProgress.seed_urls_total ?? 0}
                </div>
                <div className="text-slate-500">Seed URLs</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-white">
                  {crawlProgress.pages_found ?? 0}
                </div>
                <div className="text-slate-500">Pages discovered</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-white">
                  {crawlProgress.pages_ingested ?? 0}
                </div>
                <div className="text-slate-500">Pages fetched</div>
              </div>
              <div>
                <div className="text-lg font-semibold text-white">
                  {crawlProgress.pages_failed ?? 0}
                </div>
                <div className="text-slate-500">Pages failed</div>
              </div>
            </div>
          )}
        </Card>
      )}

      {currentStatus === 'awaiting_confirmation' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-2xl">
              👀
            </div>
            <div>
              <h3 className="font-medium text-white">Sources Found - Please Review</h3>
              <p className="text-sm text-slate-400">
                We found {status?.confirmation_summary?.total ?? 'some'} potential sources.
                Please confirm which ones are about you.
              </p>
            </div>
          </div>
        </Card>
      )}

      {currentStatus === 'ready_for_ingestion' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 text-2xl">
                ✓
              </div>
              <div>
                <h3 className="font-medium text-white">Ready for Ingestion</h3>
                <p className="text-sm text-slate-400">
                  {status?.confirmation_summary?.confirmed ?? 0} sources confirmed.
                  Continue to process them into your knowledge base.
                </p>
              </div>
            </div>
            <button
              onClick={onContinueIngestion}
              disabled={isContinuing}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors"
            >
              {isContinuing ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Starting...
                </span>
              ) : (
                'Continue'
              )}
            </button>
          </div>
        </Card>
      )}

      {currentStatus === 'ingesting' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <div className="flex-1">
              <h3 className="font-medium text-white">Processing Content</h3>
              <p className="text-sm text-slate-400">
                Extracting knowledge from your confirmed sources...
              </p>
              {status?.checkpoint_data?.ingestion && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span>Progress</span>
                    <span>
                      {status.checkpoint_data.ingestion.pages_ingested ?? status.checkpoint_data.ingestion.sources_ingested ?? 0} /{' '}
                      {status.checkpoint_data.ingestion.pages_eligible ?? status.checkpoint_data.ingestion.sources_total ?? 0} sources
                    </span>
                  </div>
                  <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all duration-500"
                      style={{
                        width: `${
                          ((status.checkpoint_data.ingestion.pages_ingested ?? status.checkpoint_data.ingestion.sources_ingested ?? 0) /
                            (status.checkpoint_data.ingestion.pages_eligible ?? status.checkpoint_data.ingestion.sources_total ?? 1)) * 100
                        }%`,
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {currentStatus === 'ingestion_completed' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 text-2xl">
                ✓
              </div>
              <div>
                <h3 className="font-medium text-white">Ingestion Complete</h3>
                <p className="text-sm text-slate-400">
                  {status?.checkpoint_data?.ingestion?.chunks_created ?? 0} knowledge chunks created.
                  {(status?.checkpoint_data?.ingestion?.words_processed ?? 0) > 0 && (
                    <> {(status?.checkpoint_data?.ingestion?.words_processed ?? 0).toLocaleString()} words ingested.</>
                  )}
                  {(status?.checkpoint_data?.ingestion?.questions_answerable_estimate ?? 0) > 0 && (
                    <> ~{(status?.checkpoint_data?.ingestion?.questions_answerable_estimate ?? 0)} answerable questions.</>
                  )}
                </p>
              </div>
            </div>
            <button
              onClick={onContinueBio}
              disabled={isContinuing}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors"
            >
              {isContinuing ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Starting...
                </span>
              ) : (
                'Generate Bio'
              )}
            </button>
          </div>
        </Card>
      )}

      {currentStatus === 'generating_bio' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <div>
              <h3 className="font-medium text-white">Generating Your Bio</h3>
              <p className="text-sm text-slate-400">
                Creating your persona's personality and voice...
              </p>
            </div>
          </div>
        </Card>
      )}

      {currentStatus === 'bio_generated' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 text-2xl">
                ✓
              </div>
              <div>
                <h3 className="font-medium text-white">Bio Generated</h3>
                <p className="text-sm text-slate-400">
                  {status?.checkpoint_data?.bio_generation?.bio_types_generated?.length ?? 0} bio variants created.
                </p>
              </div>
            </div>
            <button
              onClick={onContinueFinalize}
              disabled={isContinuing}
              className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl font-medium transition-colors"
            >
              {isContinuing ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Finalizing...
                </span>
              ) : (
                'Finalize'
              )}
            </button>
          </div>
        </Card>
      )}

      {currentStatus === 'finalizing' && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-indigo-500/20 flex items-center justify-center">
              <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            </div>
            <div>
              <h3 className="font-medium text-white">Finalizing</h3>
              <p className="text-sm text-slate-400">
                Calculating mind score and evaluating readiness...
              </p>
            </div>
          </div>
        </Card>
      )}

      {currentStatus === 'completed' && summary && (
        <Card className="p-6 bg-slate-900 border-slate-700">
          <div className="text-center">
            <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center text-green-400 text-3xl mx-auto mb-4">
              🎉
            </div>
            <h3 className="text-xl font-bold text-white mb-2">
              Your Persona is Ready!
            </h3>
            <p className="text-slate-400 mb-6">
              Here&apos;s a summary of what we built:
            </p>

            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-slate-800 p-4 rounded-lg">
                <div className="text-3xl font-bold text-indigo-400">
                  {summary.mind_score?.score ?? 0}
                </div>
                <div className="text-xs text-slate-400">Mind Score</div>
              </div>
              <div className="bg-slate-800 p-4 rounded-lg">
                <div className="text-3xl font-bold text-green-400">
                  {summary.sources.confirmed.length + summary.sources.auto_confirmed.length}
                </div>
                <div className="text-xs text-slate-400">Confirmed Sources</div>
              </div>
              <div className="bg-slate-800 p-4 rounded-lg">
                <div className="text-3xl font-bold text-amber-400">
                  {summary.readiness?.readiness_score ?? 0}%
                </div>
                <div className="text-xs text-slate-400">Readiness</div>
              </div>
            </div>

            {summary.readiness?.is_ready ? (
              <div className="text-green-400 text-sm">
                ✓ Your persona is ready to chat!
              </div>
            ) : (
              <div className="text-amber-400 text-sm">
                ⚠️ Your persona can chat but may need more sources for better responses.
              </div>
            )}
          </div>
        </Card>
      )}

      {currentStatus === 'failed' && (
        <Card className="p-6 bg-red-500/10 border-red-500/30">
          <div className="text-center">
            <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 text-3xl mx-auto mb-4">
              ✕
            </div>
            <h3 className="text-xl font-bold text-red-400 mb-2">
              Research Failed
            </h3>
            <p className="text-red-400/80 mb-4">
              The research pipeline stopped before your persona could finish processing.
            </p>
            {failureReason && (
              <div className="mb-4 rounded-lg border border-red-500/20 bg-slate-950/40 p-3 text-left text-sm text-slate-300">
                {failureReason}
              </div>
            )}
            <button
              onClick={onRetry}
              className="px-6 py-3 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-xl font-medium transition-colors"
            >
              Try Again
            </button>
          </div>
        </Card>
      )}

      {/* Polling Indicator */}
      {isPolling && !isTerminalStatus(currentStatus || 'planning') && (
        <div className="flex items-center justify-center gap-2 text-xs text-slate-500">
          <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
          Updating...
        </div>
      )}

      {/* Next Actions */}
      {hasNextAction && !isTerminalStatus(currentStatus || 'planning') && (
        <div className="text-center text-xs text-slate-500">
          Next: {nextActions.join(', ')}
        </div>
      )}
    </div>
  );
}

export default ResearchProgress;
