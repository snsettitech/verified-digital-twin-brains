/**
 * ResearchConfirmation Component (Phase 7)
 * 
 * Displays pending sources for user confirmation/rejection.
 * Supports single actions and bulk actions.
 */

'use client';

import { useState, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import {
  researchApi,
  PendingConfirmationItem,
  ContentQuality,
  getContentQualityInfo,
  getStatusLabel,
} from '@/lib/api/research';

interface ResearchConfirmationProps {
  twinId: string;
  researchRunId: string;
  pendingConfirmations: PendingConfirmationItem[];
  confirmationSummary?: {
    total: number;
    pending: number;
    auto_confirmed: number;
    manual_review: number;
  } | null;
  onConfirmationsUpdated: () => Promise<void>;
  onContinue: () => void;
}

export function ResearchConfirmation({
  twinId,
  researchRunId,
  pendingConfirmations,
  confirmationSummary,
  onConfirmationsUpdated,
  onContinue,
}: ResearchConfirmationProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Toggle selection for bulk actions
  const toggleSelection = useCallback((confirmationId: string) => {
    setSelectedIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(confirmationId)) {
        newSet.delete(confirmationId);
      } else {
        newSet.add(confirmationId);
      }
      return newSet;
    });
  }, []);

  // Select/deselect all
  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === pendingConfirmations.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingConfirmations.map(c => c.confirmation_id)));
    }
  }, [pendingConfirmations, selectedIds.size]);

  // Handle single confirm/reject
  const handleResolve = useCallback(async (
    confirmationId: string,
    action: 'confirm' | 'reject'
  ) => {
    setProcessingIds(prev => new Set(prev).add(confirmationId));
    setError(null);

    try {
      await researchApi.resolveConfirmation(twinId, researchRunId, confirmationId, {
        action,
      });
      
      // Remove from selected if present
      setSelectedIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(confirmationId);
        return newSet;
      });
      
      // Refresh parent data
      await onConfirmationsUpdated();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to process';
      setError(msg);
      console.error('Confirmation error:', err);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(confirmationId);
        return newSet;
      });
    }
  }, [twinId, researchRunId, onConfirmationsUpdated]);

  // Handle bulk confirm/reject
  const handleBulkResolve = useCallback(async (action: 'confirm' | 'reject') => {
    if (selectedIds.size === 0) return;

    setBulkProcessing(true);
    setError(null);

    try {
      await researchApi.bulkResolveConfirmations(twinId, researchRunId, {
        confirmation_ids: Array.from(selectedIds),
        action,
      });
      
      setSelectedIds(new Set());
      await onConfirmationsUpdated();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to process bulk action';
      setError(msg);
      console.error('Bulk confirmation error:', err);
    } finally {
      setBulkProcessing(false);
    }
  }, [twinId, researchRunId, selectedIds, onConfirmationsUpdated]);

  // Get quality badge
  const QualityBadge = ({ quality }: { quality: ContentQuality }) => {
    const info = getContentQualityInfo(quality);
    const colorClasses = {
      green: 'bg-green-500/20 text-green-400 border-green-500/30',
      yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      red: 'bg-red-500/20 text-red-400 border-red-500/30',
      gray: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    };

    return (
      <span className={`px-2 py-1 text-xs rounded border ${colorClasses[info.color]}`}>
        {info.label}
      </span>
    );
  };

  // Check if manual source upload is needed
  const needsManualUpload = (quality: ContentQuality) => {
    return ['blocked', 'gated', 'partial', 'error'].includes(quality);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">
          Review Discovered Sources
        </h2>
        <p className="text-slate-400">
          Confirm which sources are about you. We found{' '}
          {confirmationSummary?.total ?? pendingConfirmations.length} potential sources.
        </p>
      </div>

      {/* Summary Stats */}
      {confirmationSummary && (
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-slate-800 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-white">{confirmationSummary.total}</div>
            <div className="text-xs text-slate-400">Total</div>
          </div>
          <div className="bg-green-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-400">{confirmationSummary.auto_confirmed}</div>
            <div className="text-xs text-slate-400">Auto-Confirmed</div>
          </div>
          <div className="bg-amber-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-amber-400">{confirmationSummary.pending}</div>
            <div className="text-xs text-slate-400">Pending</div>
          </div>
          <div className="bg-red-500/10 p-3 rounded-lg text-center">
            <div className="text-2xl font-bold text-red-400">{confirmationSummary.manual_review}</div>
            <div className="text-xs text-slate-400">Manual Review</div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-red-400 text-xs underline mt-1 hover:text-red-300"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Bulk Actions */}
      {pendingConfirmations.length > 0 && (
        <div className="flex items-center justify-between bg-slate-800 p-3 rounded-lg">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={selectedIds.size === pendingConfirmations.length && pendingConfirmations.length > 0}
              onChange={toggleSelectAll}
              className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500"
            />
            <span className="text-sm text-slate-300">
              {selectedIds.size} selected
            </span>
          </div>
          
          {selectedIds.size > 0 && (
            <div className="flex gap-2">
              <button
                onClick={() => handleBulkResolve('reject')}
                disabled={bulkProcessing}
                className="px-3 py-1.5 text-sm bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded transition-colors disabled:opacity-50"
              >
                {bulkProcessing ? '...' : 'Reject All'}
              </button>
              <button
                onClick={() => handleBulkResolve('confirm')}
                disabled={bulkProcessing}
                className="px-3 py-1.5 text-sm bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded transition-colors disabled:opacity-50"
              >
                {bulkProcessing ? '...' : 'Confirm All'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Sources List */}
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {pendingConfirmations.length === 0 ? (
          <Card className="p-8 bg-slate-900 border-slate-700 text-center">
            <div className="text-4xl mb-3">✓</div>
            <h3 className="text-lg font-medium text-white mb-1">
              All Sources Reviewed
            </h3>
            <p className="text-slate-400 text-sm">
              You&apos;ve confirmed all sources. Continue to build your persona.
            </p>
          </Card>
        ) : (
          pendingConfirmations.map((item) => (
            <Card
              key={item.confirmation_id}
              className={`p-4 bg-slate-900 border-slate-700 transition-all ${
                selectedIds.has(item.confirmation_id) ? 'border-blue-500/50 ring-1 ring-blue-500/20' : ''
              }`}
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.confirmation_id)}
                  onChange={() => toggleSelection(item.confirmation_id)}
                  className="w-4 h-4 mt-1 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500"
                />
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="font-medium text-white truncate">
                        {item.title || 'Untitled Source'}
                      </h4>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:text-blue-300 truncate block"
                      >
                        {item.canonical_url || item.url}
                      </a>
                    </div>
                    <QualityBadge quality={item.content_quality} />
                  </div>

                  {item.snippet && (
                    <p className="text-sm text-slate-400 mt-2 line-clamp-2">
                      {item.snippet}
                    </p>
                  )}

                  <div className="flex items-center gap-4 mt-3">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full border border-slate-700 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                        {item.status.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs text-slate-400">Identity review</span>
                    </div>

                    {needsManualUpload(item.content_quality) && (
                      <div className="flex items-center gap-1 text-amber-400 text-xs">
                        <span>⚠️</span>
                        <span>Manual upload recommended</span>
                      </div>
                    )}

                    <div className="flex-1"></div>

                    <div className="flex gap-2">
                      <button
                        onClick={() => handleResolve(item.confirmation_id, 'reject')}
                        disabled={processingIds.has(item.confirmation_id)}
                        className="px-3 py-1.5 text-sm border border-red-500/30 hover:bg-red-500/10 text-red-400 rounded transition-colors disabled:opacity-50"
                      >
                        {processingIds.has(item.confirmation_id) ? '...' : 'Not Me'}
                      </button>
                      <button
                        onClick={() => handleResolve(item.confirmation_id, 'confirm')}
                        disabled={processingIds.has(item.confirmation_id)}
                        className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors disabled:opacity-50"
                      >
                        {processingIds.has(item.confirmation_id) ? '...' : 'This is Me'}
                      </button>
                    </div>
                  </div>

                  {/* Manual Upload Guidance */}
                  {needsManualUpload(item.content_quality) && (
                    <div className="mt-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                      <p className="text-xs text-amber-400">
                        <strong>Tip:</strong> This source couldn&apos;t be fully accessed. 
                        For better results, you can paste the content directly or upload a transcript.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Continue Button */}
      {pendingConfirmations.length === 0 && (
        <button
          onClick={onContinue}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-medium transition-colors"
        >
          Continue →
        </button>
      )}
    </div>
  );
}

export default ResearchConfirmation;
