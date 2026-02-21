'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { MessageSquare, Volume2, Type, User } from 'lucide-react';

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
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 4: Communication Patterns</h2>
        <p className="text-muted-foreground">
          How does your twin express itself? Define tone, style, and voice.
        </p>
      </div>

      {/* Tone Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Volume2 className="h-5 w-5 text-primary" />
            Communication Tone
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {TONE_OPTIONS.map((tone) => (
              <button
                key={tone.id}
                onClick={() => updateField('tone', tone.id)}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  personality.tone === tone.id
                    ? 'border-primary bg-primary/5'
                    : 'border-muted bg-card hover:bg-muted/50'
                }`}
              >
                <p className="font-semibold">{tone.label}</p>
                <p className="text-sm text-muted-foreground">{tone.desc}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Response Length */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Type className="h-5 w-5 text-primary" />
            Response Length
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3">
            {LENGTH_OPTIONS.map((length) => (
              <button
                key={length.id}
                onClick={() => updateField('responseLength', length.id)}
                className={`p-4 rounded-xl border-2 text-center transition-all ${
                  personality.responseLength === length.id
                    ? 'border-primary bg-primary/5'
                    : 'border-muted bg-card hover:bg-muted/50'
                }`}
              >
                <p className="font-semibold">{length.label}</p>
                <p className="text-xs text-muted-foreground">{length.desc}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Perspective */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Perspective
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Speak in First Person</p>
              <p className="text-sm text-muted-foreground">
                Twin says &quot;I think...&quot; instead of referring to itself by name
              </p>
            </div>
            <button
              onClick={() => updateField('firstPerson', !personality.firstPerson)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                personality.firstPerson ? 'bg-primary' : 'bg-muted'
              }`}
            >
              <span
                className={`absolute top-1 left-1 w-4 h-4 bg-background rounded-full transition-transform ${
                  personality.firstPerson ? 'translate-x-6' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </CardContent>
      </Card>

      {/* Signature Phrases */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" />
            Signature Phrases
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Phrases your twin uses frequently (optional)
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={newPhrase}
              onChange={(e) => setNewPhrase(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addPhrase()}
              placeholder="e.g., Here's the thing..."
              className="flex-1 px-3 py-2 border rounded-md bg-background"
            />
            <button
              onClick={addPhrase}
              disabled={!newPhrase.trim()}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md disabled:opacity-50"
            >
              Add
            </button>
          </div>
          
          {personality.signaturePhrases?.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {personality.signaturePhrases.map((phrase) => (
                <span
                  key={phrase}
                  className="inline-flex items-center gap-1 px-3 py-1 bg-muted rounded-full text-sm"
                >
                  &quot;{phrase}&quot;
                  <button
                    onClick={() => removePhrase(phrase)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Custom Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Custom Communication Instructions</CardTitle>
          <p className="text-sm text-muted-foreground">
            Any additional instructions for how your twin should communicate
          </p>
        </CardHeader>
        <CardContent>
          <Textarea
            value={personality.customInstructions || ''}
            onChange={(e) => updateField('customInstructions', e.target.value)}
            placeholder="e.g., Always provide specific examples. Avoid corporate jargon. Use analogies to explain complex concepts."
            rows={4}
          />
        </CardContent>
      </Card>
    </motion.div>
  );
}
