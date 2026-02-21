'use client';

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { User, Briefcase, Target, Shield, Sparkles } from 'lucide-react';

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
        <p className="text-muted-foreground">
          Who is your digital twin? Define their role, expertise, and background.
        </p>
      </div>

      {/* Specialization */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Specialization
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3">
            {SPECIALIZATIONS.map((spec) => (
              <button
                key={spec.id}
                onClick={() => handleSpecializationChange(spec.id)}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  specialization === spec.id
                    ? 'border-primary bg-primary/5'
                    : 'border-muted bg-card hover:bg-muted/50'
                }`}
              >
                <span className="text-2xl mb-2 block">{spec.emoji}</span>
                <p className="font-semibold text-sm">{spec.label}</p>
                <p className="text-xs text-muted-foreground mt-1">{spec.description}</p>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Basic Identity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Basic Identity
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="twin-name">Twin Name *</Label>
            <Input
              id="twin-name"
              value={data.twinName}
              onChange={(e) => updateField('twinName', e.target.value)}
              placeholder="e.g., Alex's Twin"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="handle">Handle (optional)</Label>
            <div className="flex items-center">
              <span className="px-3 py-2 border border-r-0 rounded-l-md bg-muted text-muted-foreground">@</span>
              <Input
                id="handle"
                value={data.handle}
                onChange={(e) => updateField('handle', e.target.value.replace(/\s+/g, '').toLowerCase())}
                placeholder="alex"
                className="rounded-l-none"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tagline">Tagline (optional)</Label>
            <Input
              id="tagline"
              value={data.tagline}
              onChange={(e) => updateField('tagline', e.target.value)}
              placeholder="e.g., Startup founder sharing lessons learned"
            />
          </div>
        </CardContent>
      </Card>

      {/* Expertise */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" />
            Areas of Expertise
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="mb-3 block">Select domains</Label>
            <div className="flex flex-wrap gap-2">
              {EXPERTISE_DOMAINS.map((domain) => (
                <button
                  key={domain}
                  onClick={() => toggleDomain(domain)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                    data.expertise?.includes(domain)
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  {domain}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2 pt-4 border-t">
            <Label>Custom Expertise</Label>
            <div className="flex gap-2">
              <Input
                value={customTag}
                onChange={(e) => setCustomTag(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addCustomExpertise()}
                placeholder="Add custom area..."
              />
              <Button onClick={addCustomExpertise} disabled={!customTag}>
                Add
              </Button>
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
        </CardContent>
      </Card>

      {/* Goals */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            Goals (Next 90 Days)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[0, 1, 2].map((idx) => (
            <Input
              key={idx}
              value={data.goals90Days[idx] || ''}
              onChange={(e) => updateGoal(idx, e.target.value)}
              placeholder={`Goal ${idx + 1} (optional)`}
            />
          ))}
        </CardContent>
      </Card>

      {/* Boundaries & Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Boundaries & Preferences
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="boundaries">Boundaries (optional)</Label>
            <Textarea
              id="boundaries"
              value={data.boundaries}
              onChange={(e) => updateField('boundaries', e.target.value)}
              placeholder="What should this twin avoid? What is out of scope?"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="privacy">Privacy Constraints (optional)</Label>
            <Textarea
              id="privacy"
              value={data.privacyConstraints}
              onChange={(e) => updateField('privacyConstraints', e.target.value)}
              placeholder="List confidential topics or data that should never be exposed"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label>When Information is Insufficient</Label>
            <RadioGroup
              value={data.uncertaintyPreference}
              onValueChange={(value: 'ask' | 'infer') => updateField('uncertaintyPreference', value)}
              className="grid grid-cols-2 gap-3"
            >
              <div>
                <RadioGroupItem value="ask" id="ask" className="peer sr-only" />
                <Label
                  htmlFor="ask"
                  className="flex flex-col p-4 border rounded-lg cursor-pointer transition-all hover:bg-muted peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5"
                >
                  <span className="font-semibold">Ask Questions</span>
                  <span className="text-xs text-muted-foreground">Prefer clarification over guessing</span>
                </Label>
              </div>
              <div>
                <RadioGroupItem value="infer" id="infer" className="peer sr-only" />
                <Label
                  htmlFor="infer"
                  className="flex flex-col p-4 border rounded-lg cursor-pointer transition-all hover:bg-muted peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5"
                >
                  <span className="font-semibold">Infer Best Effort</span>
                  <span className="text-xs text-muted-foreground">Make reasonable assumptions</span>
                </Label>
              </div>
            </RadioGroup>
          </div>
        </CardContent>
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

export default function LegacyStep1Identity({
  twinName,
  handle,
  tagline,
  specialization,
  selectedDomains,
  customExpertise,
  personality,
  goals90Days,
  boundaries,
  privacyConstraints,
  uncertaintyPreference,
  onTwinNameChange,
  onHandleChange,
  onTaglineChange,
  onSpecializationChange,
  onDomainsChange,
  onCustomExpertiseChange,
  onPersonalityChange,
  onGoalsChange,
  onBoundariesChange,
  onPrivacyConstraintsChange,
  onUncertaintyPreferenceChange,
}: LegacyStep1IdentityProps) {
  // Convert legacy props to new data format
  const data: IdentityFormData = {
    twinName,
    handle,
    tagline,
    expertise: selectedDomains,
    customExpertise,
    goals90Days,
    boundaries,
    privacyConstraints,
    uncertaintyPreference,
  };

  const handleChange = (newData: IdentityFormData) => {
    if (newData.twinName !== twinName) onTwinNameChange(newData.twinName);
    if (newData.handle !== handle) onHandleChange(newData.handle);
    if (newData.tagline !== tagline) onTaglineChange(newData.tagline);
    if (newData.expertise !== selectedDomains) onDomainsChange(newData.expertise);
    if (newData.customExpertise !== customExpertise) onCustomExpertiseChange(newData.customExpertise);
    if (newData.goals90Days !== goals90Days) onGoalsChange(newData.goals90Days);
    if (newData.boundaries !== boundaries) onBoundariesChange(newData.boundaries);
    if (newData.privacyConstraints !== privacyConstraints) onPrivacyConstraintsChange(newData.privacyConstraints);
    if (newData.uncertaintyPreference !== uncertaintyPreference) onUncertaintyPreferenceChange(newData.uncertaintyPreference);
  };

  return (
    <Step1Identity
      data={data}
      onChange={handleChange}
      onSpecializationChange={onSpecializationChange}
    />
  );
}
