'use client';

import { useState } from 'react';

import { Card } from '@/components/ui/Card';

interface PersonalityData {
  tone: string;
  responseLength: string;
  firstPerson: boolean;
  customInstructions: string;
  signaturePhrases: string[];
}

interface Step4Props {
  personality: PersonalityData;
  onPersonalityChange: (data: PersonalityData) => void;
}

const TONE_OPTIONS = [
  { id: 'professional', label: 'Professional', desc: 'Formal, polished, business-appropriate' },
  { id: 'friendly', label: 'Friendly', desc: 'Warm, approachable, conversational' },
  { id: 'casual', label: 'Casual', desc: 'Relaxed, informal, like chatting with a friend' },
  { id: 'technical', label: 'Technical', desc: 'Precise, detailed, uses industry terminology' },
];

const LENGTH_OPTIONS = [
  { id: 'concise', label: 'Concise', desc: 'Brief, to the point' },
  { id: 'balanced', label: 'Balanced', desc: 'Moderate detail' },
  { id: 'detailed', label: 'Detailed', desc: 'Comprehensive explanations' },
];

export function Step4Communication({ personality, onPersonalityChange }: Step4Props) {
  const [newPhrase, setNewPhrase] = useState('');

  const updateField = <K extends keyof PersonalityData>(field: K, value: PersonalityData[K]) => {
    onPersonalityChange({ ...personality, [field]: value });
  };

  const addPhrase = () => {
    if (newPhrase.trim() && !personality.signaturePhrases?.includes(newPhrase.trim())) {
      updateField('signaturePhrases', [...(personality.signaturePhrases || []), newPhrase.trim()]);
      setNewPhrase('');
    }
  };

  const removePhrase = (phrase: string) => {
    updateField('signaturePhrases', (personality.signaturePhrases || []).filter((p) => p !== phrase));
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 4: Communication Patterns</h2>
        <p className="text-slate-400">
          How does your twin express itself? Define tone, style, and voice.
        </p>
      </div>

      {/* Tone Selection */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">🎙️</span>
          Communication Tone
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {TONE_OPTIONS.map((tone) => (
            <button
              key={tone.id}
              onClick={() => updateField('tone', tone.id)}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                personality.tone === tone.id
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
              }`}
            >
              <p className="font-semibold text-white">{tone.label}</p>
              <p className="text-sm text-slate-400">{tone.desc}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Response Length */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">📏</span>
          Response Length
        </h3>
        <div className="grid grid-cols-3 gap-3">
          {LENGTH_OPTIONS.map((length) => (
            <button
              key={length.id}
              onClick={() => updateField('responseLength', length.id)}
              className={`p-4 rounded-xl border-2 text-center transition-all ${
                personality.responseLength === length.id
                  ? 'border-indigo-500 bg-indigo-500/10'
                  : 'border-slate-700 bg-slate-800/50 hover:bg-slate-800'
              }`}
            >
              <p className="font-semibold text-white">{length.label}</p>
              <p className="text-xs text-slate-400">{length.desc}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Perspective */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-xl">👤</span>
          Perspective
        </h3>
        <div className="flex items-center justify-between p-4 border border-slate-700 rounded-xl bg-slate-800/50">
          <div>
            <p className="font-medium text-white">Speak in First Person</p>
            <p className="text-sm text-slate-400">Twin says &quot;I think...&quot; instead of referring to itself by name</p>
          </div>
          <button
            onClick={() => updateField('firstPerson', !personality.firstPerson)}
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
      </Card>

      {/* Signature Phrases */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
          <span className="text-xl">💬</span>
          Signature Phrases
        </h3>
        <p className="text-sm text-slate-400 mb-4">
          Phrases your twin uses frequently (optional)
        </p>
        <div className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={newPhrase}
              onChange={(e) => setNewPhrase(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addPhrase()}
              placeholder="e.g., Here's the thing..."
              className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={addPhrase}
              disabled={!newPhrase.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              Add
            </button>
          </div>
          
          {personality.signaturePhrases?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {personality.signaturePhrases.map((phrase) => (
                <span
                  key={phrase}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-slate-700 rounded-full text-sm text-slate-300"
                >
                  &quot;{phrase}&quot;
                  <button
                    onClick={() => removePhrase(phrase)}
                    className="text-slate-400 hover:text-white"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Custom Instructions */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-2">Custom Communication Instructions</h3>
        <p className="text-sm text-slate-400 mb-4">
          Any additional instructions for how your twin should communicate
        </p>
        <textarea
          value={personality.customInstructions || ''}
          onChange={(e) => updateField('customInstructions', e.target.value)}
          placeholder="e.g., Always provide specific examples. Avoid corporate jargon. Use analogies to explain complex concepts."
          rows={4}
          className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
        />
      </Card>
    </div>
  );
}
