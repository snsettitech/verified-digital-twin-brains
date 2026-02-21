'use client';

import { useState } from 'react';

import { Card } from '@/components/ui/Card';

interface ThinkingStyleData {
  decisionFramework: string;
  heuristics: string[];
  customHeuristics: string;
  clarifyingBehavior: 'ask' | 'infer';
  evidenceStandards: string[];
}

interface Step2Props {
  data: ThinkingStyleData;
  onChange: (data: ThinkingStyleData) => void;
}

const frameworks = [
  {
    id: 'evidence_based',
    label: 'Evidence-Based',
    description: 'Base decisions on available data and evidence. Disclose uncertainty.',
    icon: '⚖️',
  },
  {
    id: 'intuitive',
    label: 'Pattern-Recognition',
    description: 'Rely on pattern matching and intuition from experience.',
    icon: '💡',
  },
  {
    id: 'analytical',
    label: 'Analytical',
    description: 'Break down problems systematically. Use frameworks.',
    icon: '🧠',
  },
  {
    id: 'first_principles',
    label: 'First Principles',
    description: 'Question assumptions. Reason from fundamentals.',
    icon: '🎯',
  },
];

const defaultHeuristics = [
  { id: 'team_first', label: 'Team Quality First', desc: 'Prioritize founder/team quality in evaluations' },
  { id: 'market_timing', label: 'Market Timing', desc: 'Consider market timing and tailwinds' },
  { id: 'traction_focus', label: 'Traction Focus', desc: 'Prioritize evidence over projections' },
  { id: 'moat_seeker', label: 'Moat Seeker', desc: 'Look for defensibility and competitive advantages' },
  { id: 'clarify_before_eval', label: 'Clarify Before Evaluating', desc: 'Ask questions when information is insufficient' },
];

const evidenceStandards = [
  { id: 'source_credibility', label: 'Source Credibility' },
  { id: 'recency', label: 'Recency' },
  { id: 'relevance', label: 'Relevance to Query' },
  { id: 'corroboration', label: 'Multiple Sources' },
  { id: 'quantitative', label: 'Quantitative Data' },
];

export function Step2ThinkingStyle({ data, onChange }: Step2Props) {
  const [showHeuristicHelp, setShowHeuristicHelp] = useState(false);

  const updateField = <K extends keyof ThinkingStyleData>(field: K, value: ThinkingStyleData[K]) => {
    onChange({ ...data, [field]: value });
  };

  const toggleHeuristic = (heuristicId: string) => {
    const current = data.heuristics || [];
    const updated = current.includes(heuristicId)
      ? current.filter((h) => h !== heuristicId)
      : [...current, heuristicId];
    updateField('heuristics', updated);
  };

  const toggleEvidenceStandard = (standardId: string) => {
    const current = data.evidenceStandards || [];
    const updated = current.includes(standardId)
      ? current.filter((s) => s !== standardId)
      : [...current, standardId];
    updateField('evidenceStandards', updated);
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 2: Thinking Style</h2>
        <p className="text-slate-400">
          How do you think through problems? Your cognitive heuristics and decision framework.
        </p>
      </div>

      {/* Decision Framework */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Decision Framework</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {frameworks.map((framework) => (
            <button
              key={framework.id}
              onClick={() => updateField('decisionFramework', framework.id)}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                data.decisionFramework === framework.id
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <span className="text-xl">{framework.icon}</span>
                <span className="font-semibold text-white">{framework.label}</span>
              </div>
              <span className="text-sm text-slate-400">{framework.description}</span>
            </button>
          ))}
        </div>
      </Card>

      {/* Cognitive Heuristics */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Cognitive Heuristics</h3>
          <button
            onClick={() => setShowHeuristicHelp(!showHeuristicHelp)}
            className="text-slate-400 hover:text-white"
          >
            <span className="text-lg">❓</span>
          </button>
        </div>
        {showHeuristicHelp && (
          <p className="text-sm text-slate-400 mb-4">
            Heuristics are mental shortcuts you use when evaluating situations. 
            Select the ones that match how you naturally think.
          </p>
        )}
        <div className="space-y-3">
          {defaultHeuristics.map((heuristic) => (
            <div
              key={heuristic.id}
              onClick={() => toggleHeuristic(heuristic.id)}
              className={`flex items-start space-x-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                data.heuristics?.includes(heuristic.id)
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-700 hover:bg-slate-800/50'
              }`}
            >
              <div className={`w-5 h-5 rounded border flex items-center justify-center mt-0.5 ${
                data.heuristics?.includes(heuristic.id)
                  ? 'bg-indigo-500 border-indigo-500'
                  : 'border-slate-500'
              }`}>
                {data.heuristics?.includes(heuristic.id) && <span className="text-white text-xs">✓</span>}
              </div>
              <div className="flex-1">
                <p className="font-medium text-white">{heuristic.label}</p>
                <p className="text-sm text-slate-400">{heuristic.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-2 pt-4 border-t border-slate-700 mt-4">
          <label className="block text-sm font-medium text-slate-300">Additional Heuristics (Optional)</label>
          <textarea
            placeholder="Describe any other mental models or heuristics you use..."
            value={data.customHeuristics || ''}
            onChange={(e) => updateField('customHeuristics', e.target.value)}
            rows={3}
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
          />
        </div>
      </Card>

      {/* Clarifying Behavior */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">When Information is Insufficient</h3>
        <div className="space-y-3">
          <div
            onClick={() => updateField('clarifyingBehavior', 'ask')}
            className={`flex items-start space-x-3 p-3 border rounded-lg cursor-pointer transition-colors ${
              data.clarifyingBehavior === 'ask'
                ? 'border-indigo-500 bg-indigo-500/10'
                : 'border-slate-700 hover:bg-slate-800/50'
            }`}
          >
            <div className={`w-5 h-5 rounded-full border flex items-center justify-center mt-0.5 ${
              data.clarifyingBehavior === 'ask'
                ? 'bg-indigo-500 border-indigo-500'
                : 'border-slate-500'
            }`}>
              {data.clarifyingBehavior === 'ask' && <span className="text-white text-xs">●</span>}
            </div>
            <div className="flex-1">
              <p className="font-medium text-white">Ask Clarifying Questions</p>
              <p className="text-sm text-slate-400">
                When uncertain, ask the user for more information before giving an assessment.
              </p>
            </div>
          </div>
          <div
            onClick={() => updateField('clarifyingBehavior', 'infer')}
            className={`flex items-start space-x-3 p-3 border rounded-lg cursor-pointer transition-colors ${
              data.clarifyingBehavior === 'infer'
                ? 'border-indigo-500 bg-indigo-500/10'
                : 'border-slate-700 hover:bg-slate-800/50'
            }`}
          >
            <div className={`w-5 h-5 rounded-full border flex items-center justify-center mt-0.5 ${
              data.clarifyingBehavior === 'infer'
                ? 'bg-indigo-500 border-indigo-500'
                : 'border-slate-500'
            }`}>
              {data.clarifyingBehavior === 'infer' && <span className="text-white text-xs">●</span>}
            </div>
            <div className="flex-1">
              <p className="font-medium text-white">Infer Best Effort</p>
              <p className="text-sm text-slate-400">
                Make reasonable assumptions and proceed with evaluation, disclosing uncertainty.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Evidence Standards */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Evidence Standards</h3>
        <p className="text-sm text-slate-400 mb-4">
          What makes evidence credible to you?
        </p>
        <div className="grid grid-cols-2 gap-3">
          {evidenceStandards.map((standard) => (
            <div
              key={standard.id}
              onClick={() => toggleEvidenceStandard(standard.id)}
              className="flex items-center space-x-2 cursor-pointer"
            >
              <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                data.evidenceStandards?.includes(standard.id)
                  ? 'bg-indigo-500 border-indigo-500'
                  : 'border-slate-500'
              }`}>
                {data.evidenceStandards?.includes(standard.id) && <span className="text-white text-xs">✓</span>}
              </div>
              <span className="text-sm text-slate-300">{standard.label}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
