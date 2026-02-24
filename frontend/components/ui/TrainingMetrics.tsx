'use client';

import React from 'react';

/**
 * Training Metrics Display Component
 * 
 * Delphi-style profile training metrics:
 * - Words Processed (e.g., 167.1K)
 * - Questions Answerable (e.g., 2.1K)
 * - Mind Score (0-100 with label)
 * 
 * V1 Heuristic Implementation:
 * These are estimated metrics based on content volume, diversity, and extraction quality.
 * They are NOT literal counts of validated questions.
 */

export interface TrainingMetricsData {
  words_processed: number;
  words_processed_display: string;
  questions_answerable_est: number;
  questions_answerable_display: string;
  mind_score: number;
  mind_score_label: string;
  method_version?: string;
  last_computed_at?: string;
  notes?: string;
}

interface TrainingMetricsProps {
  metrics?: TrainingMetricsData | null;
  isLoading?: boolean;
  showLabels?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: {
    container: 'gap-3',
    card: 'px-3 py-2',
    value: 'text-lg',
    label: 'text-xs',
    subtext: 'text-[10px]',
  },
  md: {
    container: 'gap-4',
    card: 'px-4 py-3',
    value: 'text-2xl',
    label: 'text-sm',
    subtext: 'text-xs',
  },
  lg: {
    container: 'gap-6',
    card: 'px-6 py-4',
    value: 'text-3xl',
    label: 'text-base',
    subtext: 'text-sm',
  },
};

function getScoreColor(score: number): string {
  if (score >= 75) return 'text-emerald-600';
  if (score >= 55) return 'text-blue-600';
  if (score >= 35) return 'text-amber-600';
  if (score >= 15) return 'text-orange-600';
  return 'text-slate-500';
}

function getScoreBgColor(score: number): string {
  if (score >= 75) return 'bg-emerald-500';
  if (score >= 55) return 'bg-blue-500';
  if (score >= 35) return 'bg-amber-500';
  if (score >= 15) return 'bg-orange-500';
  return 'bg-slate-400';
}

export function TrainingMetrics({
  metrics,
  isLoading = false,
  showLabels = true,
  size = 'md',
  className = '',
}: TrainingMetricsProps) {
  const sizes = sizeClasses[size];

  if (isLoading) {
    return (
      <div className={`flex ${sizes.container} ${className}`}>
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className={`flex-1 animate-pulse rounded-xl bg-slate-100 ${sizes.card}`}
          >
            <div className={`h-6 w-16 rounded bg-slate-200 ${i === 3 ? 'mb-2' : ''}`} />
            {i === 3 && <div className="h-4 w-20 rounded bg-slate-200" />}
          </div>
        ))}
      </div>
    );
  }

  // Default/empty state
  const displayMetrics: TrainingMetricsData = metrics || {
    words_processed: 0,
    words_processed_display: '0',
    questions_answerable_est: 0,
    questions_answerable_display: '0',
    mind_score: 0,
    mind_score_label: 'Early',
  };

  const { 
    words_processed_display, 
    questions_answerable_display, 
    mind_score, 
    mind_score_label 
  } = displayMetrics;

  const scoreColor = getScoreColor(mind_score);
  const scoreBgColor = getScoreBgColor(mind_score);

  return (
    <div className={`flex ${sizes.container} ${className}`}>
      {/* Words Processed */}
      <div
        className={`flex-1 rounded-xl border border-slate-200 bg-white/80 ${sizes.card} shadow-sm`}
        title="Total words extracted and processed from ingested sources"
      >
        <div className={`font-bold text-slate-900 ${sizes.value}`}>
          {words_processed_display}
        </div>
        {showLabels && (
          <div className={`font-medium text-slate-500 ${sizes.label}`}>
            Words Processed
          </div>
        )}
      </div>

      {/* Questions Answerable */}
      <div
        className={`flex-1 rounded-xl border border-slate-200 bg-white/80 ${sizes.card} shadow-sm`}
        title="Estimated number of questions the twin can answer based on content coverage"
      >
        <div className={`font-bold text-slate-900 ${sizes.value}`}>
          {questions_answerable_display}
        </div>
        {showLabels && (
          <div className={`font-medium text-slate-500 ${sizes.label}`}>
            Questions Answerable
          </div>
        )}
      </div>

      {/* Mind Score */}
      <div
        className={`flex-1 rounded-xl border border-slate-200 bg-white/80 ${sizes.card} shadow-sm`}
        title="Training completeness score (0-100)"
      >
        <div className={`flex items-baseline gap-2`}>
          <span className={`font-bold ${scoreColor} ${sizes.value}`}>
            {mind_score}
          </span>
          <span className={`${sizes.subtext} font-medium text-slate-400`}>
            /100
          </span>
        </div>
        {showLabels && (
          <div className="flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${scoreBgColor}`} />
            <span className={`font-medium text-slate-600 ${sizes.label}`}>
              {mind_score_label}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Compact version for header/navigation use
 */
export function TrainingMetricsCompact({
  metrics,
  isLoading = false,
  className = '',
}: Omit<TrainingMetricsProps, 'size' | 'showLabels'>) {
  if (isLoading) {
    return (
      <div className={`flex items-center gap-3 rounded-full bg-white/80 px-3 py-1.5 shadow-sm ${className}`}>
        <div className="h-4 w-16 animate-pulse rounded bg-slate-200" />
      </div>
    );
  }

  const displayMetrics: TrainingMetricsData = metrics || {
    words_processed: 0,
    words_processed_display: '0',
    questions_answerable_est: 0,
    questions_answerable_display: '0',
    mind_score: 0,
    mind_score_label: 'Early',
  };

  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-sm ${className}`}
      title={`${displayMetrics.words_processed_display} words • ${displayMetrics.questions_answerable_display} questions • Score: ${displayMetrics.mind_score}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${getScoreBgColor(displayMetrics.mind_score)}`} />
      <span>{displayMetrics.mind_score_label}</span>
      <span className="text-slate-400">|</span>
      <span>{displayMetrics.words_processed_display}</span>
    </div>
  );
}

/**
 * Single metric card for flexible layouts
 */
interface MetricCardProps {
  value: string | number;
  label: string;
  subtext?: string;
  color?: 'default' | 'primary' | 'success' | 'warning';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function MetricCard({
  value,
  label,
  subtext,
  color = 'default',
  size = 'md',
  className = '',
}: MetricCardProps) {
  const sizes = sizeClasses[size];

  const colorClasses = {
    default: 'border-slate-200 bg-white/80 text-slate-900',
    primary: 'border-orange-200 bg-orange-50/80 text-orange-900',
    success: 'border-emerald-200 bg-emerald-50/80 text-emerald-900',
    warning: 'border-amber-200 bg-amber-50/80 text-amber-900',
  };

  return (
    <div
      className={`rounded-xl border ${colorClasses[color]} ${sizes.card} shadow-sm ${className}`}
    >
      <div className={`font-bold ${sizes.value}`}>{value}</div>
      <div className={`font-medium text-slate-500 ${sizes.label}`}>{label}</div>
      {subtext && (
        <div className={`mt-1 text-slate-400 ${sizes.subtext}`}>{subtext}</div>
      )}
    </div>
  );
}

export default TrainingMetrics;
