'use client';

export type ProgressStepStatus = 'pending' | 'running' | 'done' | 'skipped' | 'failed';

export interface ProgressStep {
  id: string;
  label: string;
  sublabel?: string;
  status: ProgressStepStatus;
}

interface StepProgressProps {
  name: string;
  steps: ProgressStep[];
}

const RESEARCH_LABELS: Record<string, string> = {
  created:      'Starting research…',
  searching:    'Searching the web…',
  crawling:     'Reading public content…',
  extracting:   'Extracting information…',
  synthesizing: 'Building profile…',
  completed:    'Research complete',
  failed:       'Research failed',
};

export function getResearchStepLabel(status: string): string {
  return RESEARCH_LABELS[status] ?? status;
}

function StepIcon({ status }: { status: ProgressStepStatus }) {
  if (status === 'done') {
    return (
      <div className="w-7 h-7 rounded-full bg-green-500/20 border border-green-500/40 flex items-center justify-center shrink-0">
        <svg className="w-3.5 h-3.5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }
  if (status === 'running') {
    return (
      <div className="w-7 h-7 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center shrink-0">
        <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (status === 'failed') {
    return (
      <div className="w-7 h-7 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center shrink-0">
        <svg className="w-3.5 h-3.5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </div>
    );
  }
  if (status === 'skipped') {
    return (
      <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
      </div>
    );
  }
  // pending
  return (
    <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
      <span className="w-1.5 h-1.5 rounded-full bg-slate-700" />
    </div>
  );
}

export function StepProgress({ name, steps }: StepProgressProps) {
  const doneCount = steps.filter(s => s.status === 'done').length;
  const total = steps.filter(s => s.status !== 'skipped').length;
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-white">Building {name}&apos;s Persona</h2>
          <p className="text-slate-400 text-sm mt-1">This takes about a minute</p>
        </div>

        {/* Progress bar */}
        <div className="mb-6">
          <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Steps */}
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div
              key={step.id}
              className={`flex items-center gap-3 transition-opacity duration-300 ${
                step.status === 'skipped' ? 'opacity-30' : 'opacity-100'
              }`}
            >
              {/* Connector line */}
              <div className="relative">
                <StepIcon status={step.status} />
                {i < steps.length - 1 && (
                  <div className="absolute top-7 left-1/2 -translate-x-px w-px h-3 bg-slate-800" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${
                  step.status === 'done'    ? 'text-slate-300' :
                  step.status === 'running' ? 'text-white' :
                  step.status === 'failed'  ? 'text-red-400' :
                  'text-slate-600'
                }`}>
                  {step.label}
                </p>
                {step.sublabel && step.status === 'running' && (
                  <p className="text-xs text-slate-500 mt-0.5 truncate">{step.sublabel}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
