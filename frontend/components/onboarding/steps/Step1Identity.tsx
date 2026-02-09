'use client';

import React, { useState, useEffect } from 'react';

interface Step1IdentityProps {
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
  onTwinNameChange: (value: string) => void;
  onHandleChange: (value: string) => void;
  onTaglineChange: (value: string) => void;
  onSpecializationChange: (value: string) => void;
  onDomainsChange: (domains: string[]) => void;
  onCustomExpertiseChange: (expertise: string[]) => void;
  onPersonalityChange: (personality: any) => void;
}

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

export default function Step1Identity({
  twinName,
  handle,
  tagline,
  specialization,
  selectedDomains,
  customExpertise,
  personality,
  onTwinNameChange,
  onHandleChange,
  onTaglineChange,
  onSpecializationChange,
  onDomainsChange,
  onCustomExpertiseChange,
  onPersonalityChange,
}: Step1IdentityProps) {
  const [customTag, setCustomTag] = useState('');
  const [activeTab, setActiveTab] = useState<'basic' | 'expertise' | 'personality'>('basic');

  const toggleDomain = (domain: string) => {
    if (selectedDomains.includes(domain)) {
      onDomainsChange(selectedDomains.filter(d => d !== domain));
    } else {
      onDomainsChange([...selectedDomains, domain]);
    }
  };

  const addCustomExpertise = () => {
    if (customTag && !customExpertise.includes(customTag)) {
      onCustomExpertiseChange([...customExpertise, customTag]);
      setCustomTag('');
    }
  };

  const removeCustomExpertise = (tag: string) => {
    onCustomExpertiseChange(customExpertise.filter(t => t !== tag));
  };

  return (
    <div className="space-y-6">
      {/* Welcome Header */}
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">Create Your Digital Twin</h2>
        <p className="text-slate-400">Let&apos;s set up your AI in 3 simple steps</p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 p-1 bg-white/5 rounded-xl mb-6">
        {(['basic', 'expertise', 'personality'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab
                ? 'bg-indigo-600 text-white'
                : 'text-slate-400 hover:text-white hover:bg-white/5'
            }`}
          >
            {tab === 'basic' && 'Basic Info'}
            {tab === 'expertise' && 'Expertise'}
            {tab === 'personality' && 'Personality'}
          </button>
        ))}
      </div>

      {/* Basic Info Tab */}
      {activeTab === 'basic' && (
        <div className="space-y-6 animate-fadeIn">
          {/* Twin Type Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">What type of twin?</label>
            <div className="grid grid-cols-2 gap-3">
              {SPECIALIZATIONS.map((spec) => (
                <button
                  key={spec.id}
                  onClick={() => onSpecializationChange(spec.id)}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    specialization === spec.id
                      ? 'border-indigo-500 bg-indigo-500/10'
                      : 'border-white/10 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <span className="text-2xl mb-2 block">{spec.emoji}</span>
                  <p className="font-semibold text-white text-sm">{spec.label}</p>
                  <p className="text-xs text-slate-400 mt-1">{spec.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Identity Fields */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Twin Name</label>
              <input
                type="text"
                value={twinName}
                onChange={(e) => onTwinNameChange(e.target.value)}
                placeholder="e.g., Alex's Twin"
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Handle (optional)</label>
              <div className="flex items-center bg-white/5 border border-white/10 rounded-xl px-4">
                <span className="text-slate-500">@</span>
                <input
                  type="text"
                  value={handle}
                  onChange={(e) => onHandleChange(e.target.value.replace(/\s+/g, '').toLowerCase())}
                  placeholder="alex"
                  className="flex-1 px-2 py-3 bg-transparent text-white placeholder-slate-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Tagline (optional)</label>
              <input
                type="text"
                value={tagline}
                onChange={(e) => onTaglineChange(e.target.value)}
                placeholder="e.g., Startup founder sharing lessons learned"
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
          </div>
        </div>
      )}

      {/* Expertise Tab */}
      {activeTab === 'expertise' && (
        <div className="space-y-6 animate-fadeIn">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">Areas of Expertise</label>
            <p className="text-xs text-slate-400 mb-3">Select domains your twin should know about</p>
            <div className="flex flex-wrap gap-2">
              {EXPERTISE_DOMAINS.map((domain) => (
                <button
                  key={domain}
                  onClick={() => toggleDomain(domain)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                    selectedDomains.includes(domain)
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  {domain}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Expertise Tags */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Custom Expertise</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customTag}
                onChange={(e) => setCustomTag(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addCustomExpertise()}
                placeholder="Add custom area..."
                className="flex-1 px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                onClick={addCustomExpertise}
                disabled={!customTag}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-medium transition-colors"
              >
                Add
              </button>
            </div>
            {customExpertise.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {customExpertise.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-600/20 text-emerald-400 rounded-lg text-sm"
                  >
                    {tag}
                    <button
                      onClick={() => removeCustomExpertise(tag)}
                      className="hover:text-emerald-300"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Personality Tab */}
      {activeTab === 'personality' && (
        <div className="space-y-6 animate-fadeIn">
          {/* Tone Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">Communication Tone</label>
            <div className="grid grid-cols-2 gap-3">
              {[
                { id: 'professional', label: 'Professional', desc: 'Formal and polished' },
                { id: 'friendly', label: 'Friendly', desc: 'Warm and approachable' },
                { id: 'casual', label: 'Casual', desc: 'Relaxed and conversational' },
                { id: 'technical', label: 'Technical', desc: 'Precise and detailed' },
              ].map((tone) => (
                <button
                  key={tone.id}
                  onClick={() => onPersonalityChange({ ...personality, tone: tone.id })}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    personality.tone === tone.id
                      ? 'border-indigo-500 bg-indigo-500/10'
                      : 'border-white/10 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <p className="font-medium text-white text-sm">{tone.label}</p>
                  <p className="text-xs text-slate-400">{tone.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Response Length */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3">Response Length</label>
            <div className="flex gap-2">
              {[
                { id: 'concise', label: 'Concise' },
                { id: 'balanced', label: 'Balanced' },
                { id: 'detailed', label: 'Detailed' },
              ].map((length) => (
                <button
                  key={length.id}
                  onClick={() => onPersonalityChange({ ...personality, responseLength: length.id })}
                  className={`flex-1 py-2 px-4 rounded-xl text-sm font-medium transition-all ${
                    personality.responseLength === length.id
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
                  }`}
                >
                  {length.label}
                </button>
              ))}
            </div>
          </div>

          {/* First Person Toggle */}
          <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/10">
            <div>
              <p className="font-medium text-white">Speak in First Person</p>
              <p className="text-sm text-slate-400">Twin says &quot;I think...&quot; instead of &quot;{twinName || 'Alex'} thinks...&quot;</p>
            </div>
            <button
              onClick={() => onPersonalityChange({ ...personality, firstPerson: !personality.firstPerson })}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                personality.firstPerson ? 'bg-indigo-600' : 'bg-slate-600'
              }`}
            >
              <span
                className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${
                  personality.firstPerson ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>
      )}

      {/* Summary Footer */}
      <div className="pt-4 border-t border-white/10">
        <div className="flex items-center gap-4 text-sm">
          <div className="flex-1">
            <p className="text-slate-400">Ready to continue?</p>
            <p className="text-white font-medium">
              {twinName || 'Your Twin'} • {specialization ? SPECIALIZATIONS.find(s => s.id === specialization)?.label : 'General'} • {selectedDomains.length + customExpertise.length} expertise areas
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
