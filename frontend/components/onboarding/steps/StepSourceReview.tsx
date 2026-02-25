'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';

export type SourceType = 'linkedin' | 'youtube' | 'instagram' | 'tiktok' | 'website' | 'export' | 'paste' | 'other';

export interface ReviewSource {
  type: string;
  value: string;
  status?: string;
}

function detectSourceType(urlOrValue: string): SourceType {
  const t = (urlOrValue || '').toLowerCase();
  if (t.includes('linkedin.com')) return 'linkedin';
  if (t.includes('youtube.com') || t.includes('youtu.be')) return 'youtube';
  if (t.includes('instagram.com')) return 'instagram';
  if (t.includes('tiktok.com')) return 'tiktok';
  if (t.startsWith('http://') || t.startsWith('https://')) return 'website';
  if (t.endsWith('.zip') || t.endsWith('.pdf') || t.endsWith('.html')) return 'export';
  return 'other';
}

function getSourceTypeLabel(type: SourceType): string {
  const labels: Record<SourceType, string> = {
    linkedin: 'LinkedIn',
    youtube: 'YouTube',
    instagram: 'Instagram',
    tiktok: 'TikTok',
    website: 'Website',
    export: 'Export',
    paste: 'Pasted Content',
    other: 'Other',
  };
  return labels[type] || type;
}

interface StepSourceReviewProps {
  sources: ReviewSource[];
  onSubmit: () => void;
  onBack: () => void;
}

export function StepSourceReview({ sources, onSubmit, onBack }: StepSourceReviewProps) {
  const [consentOwnership, setConsentOwnership] = useState(false);
  const [consentIngestion, setConsentIngestion] = useState(false);
  const [consentPlatformVariation, setConsentPlatformVariation] = useState(false);
  const [consentRemoval, setConsentRemoval] = useState(false);

  const allConsented =
    consentOwnership && consentIngestion && consentPlatformVariation && consentRemoval;

  const handleSubmit = () => {
    if (!allConsented) return;
    onSubmit();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">Review Your Sources</h2>
        <p className="text-slate-400">
          Confirm the sources we&apos;ll ingest and agree to the terms before building your digital brain.
        </p>
      </div>

      {/* Sources to ingest */}
      <Card className="p-6 bg-slate-900 border-slate-700">
        <h3 className="font-semibold text-white mb-4">Sources to ingest</h3>
        <div className="space-y-3 max-h-48 overflow-y-auto">
          {sources.length === 0 ? (
            <p className="text-slate-500 text-sm">No sources added.</p>
          ) : (
            sources.map((source, idx) => {
              const detectedType =
                source.type === 'paste'
                  ? 'paste'
                  : source.type === 'export'
                    ? 'export'
                    : detectSourceType(source.value);
              const displayValue =
                source.type === 'paste'
                  ? `${source.value.slice(0, 60)}${source.value.length > 60 ? '...' : ''}`
                  : source.value;
              return (
                <div
                  key={idx}
                  className="flex items-center justify-between gap-3 py-2 border-b border-slate-800 last:border-0"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-300 shrink-0"
                    >
                      {getSourceTypeLabel(detectedType)}
                    </span>
                    <span className="text-sm text-slate-400 truncate" title={source.value}>
                      {displayValue}
                    </span>
                  </div>
                  <span className="text-xs text-green-400 shrink-0">
                    {source.status || 'Ready'}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </Card>

      {/* Consent checkboxes */}
      <Card className="p-6 bg-slate-900 border-slate-700">
        <h3 className="font-semibold text-white mb-4">Consent & permissions</h3>
        <div className="space-y-4">
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={consentOwnership}
              onChange={(e) => setConsentOwnership(e.target.checked)}
              className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/20"
            />
            <span className="text-sm text-slate-300 group-hover:text-slate-200">
              I confirm I own or am authorized to connect these sources
            </span>
          </label>
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={consentIngestion}
              onChange={(e) => setConsentIngestion(e.target.checked)}
              className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/20"
            />
            <span className="text-sm text-slate-300 group-hover:text-slate-200">
              I agree to data ingestion and processing for building my digital brain
            </span>
          </label>
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={consentPlatformVariation}
              onChange={(e) => setConsentPlatformVariation(e.target.checked)}
              className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/20"
            />
            <span className="text-sm text-slate-300 group-hover:text-slate-200">
              I understand platform/API access may vary by source
            </span>
          </label>
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={consentRemoval}
              onChange={(e) => setConsentRemoval(e.target.checked)}
              className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/20"
            />
            <span className="text-sm text-slate-300 group-hover:text-slate-200">
              I can remove data later
            </span>
          </label>
        </div>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="px-6 py-3 border border-slate-700 hover:bg-slate-800 text-slate-300 rounded-xl font-medium transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleSubmit}
          disabled={!allConsented}
          className="flex-1 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
        >
          Build My Digital Brain
        </button>
      </div>
    </div>
  );
}
