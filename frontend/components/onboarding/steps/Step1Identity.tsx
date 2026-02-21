'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';

// =============================================================================
// Types
// =============================================================================

export interface IdentityFormData {
  twinName: string;
  handle: string;
  tagline: string;
  expertise: string[];
  customExpertise: string[];
  goals90Days: string[];
  boundaries: string;
  privacyConstraints: string;
  uncertaintyPreference: 'ask' | 'infer';
}

interface Step1Props {
  data: IdentityFormData;
  onChange: (data: IdentityFormData) => void;
  onSpecializationChange?: (specialization: string) => void;
}

// =============================================================================
// Constants
// =============================================================================

const SPECIALIZATIONS = [
  { id: 'vanilla', label: 'General Purpose', emoji: '🧠', description: 'A well-rounded digital twin for general knowledge' },
  { id: 'founder', label: 'Founder', emoji: '🚀', description: 'Share your startup journey and business insights' },
  { id: 'creator', label: 'Creator', emoji: '🎨', description: 'For artists, writers, and content creators' },
  { id: 'technical', label: 'Technical Expert', emoji: '⚡', description: 'Deep technical knowledge and engineering expertise' },
];

const EXPERTISE_DOMAINS = [
  'Business Strategy',
  'Product Management',
  'Engineering',
  'Design',
  'Marketing',
  'Sales',
  'Operations',
  'Finance',
  'Leadership',
  'Startup Growth',
  'AI/ML',
  'Web Development',
  'Mobile Development',
  'UX Research',
  'Content Strategy',
];

// =============================================================================
// Component
// =============================================================================

export function Step1Identity({ data, onChange, onSpecializationChange }: Step1Props) {
  const [customTag, setCustomTag] = useState('');
  const [specialization, setSpecialization] = useState('vanilla');

  const updateField = <K extends keyof IdentityFormData>(field: K, value: IdentityFormData[K]) => {
    onChange({ ...data, [field]: value });
  };

  const handleSpecializationChange = (spec: string) => {
    setSpecialization(spec);
    onSpecializationChange?.(spec);
  };

  const toggleDomain = (domain: string) => {
    const current = data.expertise || [];
    const updated = current.includes(domain)
      ? current.filter((d) => d !== domain)
      : [...current, domain];
    updateField('expertise', updated);
  };

  const addCustomExpertise = () => {
    if (customTag && !data.customExpertise.includes(customTag)) {
      updateField('customExpertise', [...data.customExpertise, customTag]);
      setCustomTag('');
    }
  };

  const removeCustomExpertise = (tag: string) => {
    updateField('customExpertise', data.customExpertise.filter((t) => t !== tag));
  };

  const updateGoal = (index: number, value: string) => {
    const newGoals = [...data.goals90Days];
    newGoals[index] = value;
    updateField('goals90Days', newGoals);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 1: Identity Frame</h2>
        <p className="text-slate-400">
          Who is your digital twin? Define their role, expertise, and background.
        </p>
      </div>

      {/* Specialization */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">✨</span>
          Specialization
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {SPECIALIZATIONS.map((spec) => (
            <button
              key={spec.id}
              onClick={() => handleSpecializationChange(spec.id)}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                specialization === spec.id
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
              }`}
            >
              <span className="text-2xl mb-2 block">{spec.emoji}</span>
              <p className="font-semibold text-sm text-white">{spec.label}</p>
              <p className="text-xs text-slate-400 mt-1">{spec.description}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Basic Identity */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">👤</span>
          Basic Identity
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Twin Name *</label>
            <input
              type="text"
              value={data.twinName}
              onChange={(e) => updateField('twinName', e.target.value)}
              placeholder="e.g., Alex's Twin"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Handle (optional)</label>
            <div className="flex items-center bg-slate-800 border border-slate-700 rounded-xl px-4">
              <span className="text-slate-500">@</span>
              <input
                type="text"
                value={data.handle}
                onChange={(e) => updateField('handle', e.target.value.replace(/\s+/g, '').toLowerCase())}
                placeholder="alex"
                className="flex-1 px-2 py-3 bg-transparent text-white placeholder-slate-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Tagline (optional)</label>
            <input
              type="text"
              value={data.tagline}
              onChange={(e) => updateField('tagline', e.target.value)}
              placeholder="e.g., Startup founder sharing lessons learned"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>
      </Card>

      {/* Expertise */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">💼</span>
          Areas of Expertise
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">Select domains</label>
            <div className="flex flex-wrap gap-2">
              {EXPERTISE_DOMAINS.map((domain) => (
                <button
                  key={domain}
                  onClick={() => toggleDomain(domain)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                    data.expertise?.includes(domain)
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                  }`}
                >
                  {domain}
                </button>
              ))}
            </div>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <label className="block text-sm font-medium text-slate-300 mb-2">Custom Expertise</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customTag}
                onChange={(e) => setCustomTag(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addCustomExpertise()}
                placeholder="Add custom area..."
                className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={addCustomExpertise}
                disabled={!customTag}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium"
              >
                Add
              </button>
            </div>
            {data.customExpertise?.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {data.customExpertise.map((tag) => (
                  <Badge key={tag} variant="secondary" className="cursor-pointer" onClick={() => removeCustomExpertise(tag)}>
                    {tag} ×
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Goals */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">🎯</span>
          Goals (Next 90 Days)
        </h3>
        <div className="space-y-3">
          {[0, 1, 2].map((idx) => (
            <input
              key={idx}
              type="text"
              value={data.goals90Days[idx] || ''}
              onChange={(e) => updateGoal(idx, e.target.value)}
              placeholder={`Goal ${idx + 1} (optional)`}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          ))}
        </div>
      </Card>

      {/* Boundaries & Preferences */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">🛡️</span>
          Boundaries & Preferences
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Boundaries (optional)</label>
            <textarea
              value={data.boundaries}
              onChange={(e) => updateField('boundaries', e.target.value)}
              placeholder="What should this twin avoid? What is out of scope?"
              rows={3}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Privacy Constraints (optional)</label>
            <textarea
              value={data.privacyConstraints}
              onChange={(e) => updateField('privacyConstraints', e.target.value)}
              placeholder="List confidential topics or data that should never be exposed"
              rows={3}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">When Information is Insufficient</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => updateField('uncertaintyPreference', 'ask')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  data.uncertaintyPreference === 'ask'
                    ? 'border-indigo-500 bg-indigo-500/10'
                    : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
                }`}
              >
                <p className="font-semibold text-white">Ask Questions</p>
                <p className="text-xs text-slate-400 mt-1">Prefer clarification over guessing</p>
              </button>
              <button
                onClick={() => updateField('uncertaintyPreference', 'infer')}
                className={`p-4 rounded-xl border text-left transition-all ${
                  data.uncertaintyPreference === 'infer'
                    ? 'border-indigo-500 bg-indigo-500/10'
                    : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
                }`}
              >
                <p className="font-semibold text-white">Infer Best Effort</p>
                <p className="text-xs text-slate-400 mt-1">Make reasonable assumptions</p>
              </button>
            </div>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

// =============================================================================
// Legacy Default Export (for backwards compatibility)
// =============================================================================

interface LegacyStep1IdentityProps {
  twinName: string;
  handle: string;
  tagline: string;
  specialization: string;
  selectedDomains: string[];
  customExpertise: string[];
  personality: {
    tone: 'professional' | 'friendly' | 'casual' | 'technical';
    responseLength: 'concise' | 'balanced' | 'detailed';
    firstPerson: boolean;
    customInstructions: string;
  };
  goals90Days: string[];
  boundaries: string;
  privacyConstraints: string;
  uncertaintyPreference: 'ask' | 'infer';
  onTwinNameChange: (value: string) => void;
  onHandleChange: (value: string) => void;
  onTaglineChange: (value: string) => void;
  onSpecializationChange: (value: string) => void;
  onDomainsChange: (domains: string[]) => void;
  onCustomExpertiseChange: (expertise: string[]) => void;
  onPersonalityChange: (personality: any) => void;
  onGoalsChange: (goals: string[]) => void;
  onBoundariesChange: (value: string) => void;
  onPrivacyConstraintsChange: (value: string) => void;
  onUncertaintyPreferenceChange: (value: 'ask' | 'infer') => void;
}

export default function LegacyStep1Identity(props: LegacyStep1IdentityProps) {
  const data: IdentityFormData = {
    twinName: props.twinName,
    handle: props.handle,
    tagline: props.tagline,
    expertise: props.selectedDomains,
    customExpertise: props.customExpertise,
    goals90Days: props.goals90Days,
    boundaries: props.boundaries,
    privacyConstraints: props.privacyConstraints,
    uncertaintyPreference: props.uncertaintyPreference,
  };

  const handleChange = (newData: IdentityFormData) => {
    if (newData.twinName !== props.twinName) props.onTwinNameChange(newData.twinName);
    if (newData.handle !== props.handle) props.onHandleChange(newData.handle);
    if (newData.tagline !== props.tagline) props.onTaglineChange(newData.tagline);
    if (newData.expertise !== props.selectedDomains) props.onDomainsChange(newData.expertise);
    if (newData.customExpertise !== props.customExpertise) props.onCustomExpertiseChange(newData.customExpertise);
    if (newData.goals90Days !== props.goals90Days) props.onGoalsChange(newData.goals90Days);
    if (newData.boundaries !== props.boundaries) props.onBoundariesChange(newData.boundaries);
    if (newData.privacyConstraints !== props.privacyConstraints) props.onPrivacyConstraintsChange(newData.privacyConstraints);
    if (newData.uncertaintyPreference !== props.uncertaintyPreference) props.onUncertaintyPreferenceChange(newData.uncertaintyPreference);
  };

  return (
    <Step1Identity
      data={data}
      onChange={handleChange}
      onSpecializationChange={props.onSpecializationChange}
    />
  );
}
