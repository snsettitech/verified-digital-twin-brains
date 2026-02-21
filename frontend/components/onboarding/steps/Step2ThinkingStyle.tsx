'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import { Brain, HelpCircle, Lightbulb, Scale, Target } from 'lucide-react';

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
    icon: Scale,
  },
  {
    id: 'intuitive',
    label: 'Pattern-Recognition',
    description: 'Rely on pattern matching and intuition from experience.',
    icon: Lightbulb,
  },
  {
    id: 'analytical',
    label: 'Analytical',
    description: 'Break down problems systematically. Use frameworks.',
    icon: Brain,
  },
  {
    id: 'first_principles',
    label: 'First Principles',
    description: 'Question assumptions. Reason from fundamentals.',
    icon: Target,
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
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 2: Thinking Style</h2>
        <p className="text-muted-foreground">
          How do you think through problems? Your cognitive heuristics and decision framework.
        </p>
      </div>

      {/* Decision Framework */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Decision Framework</CardTitle>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={data.decisionFramework}
            onValueChange={(value) => updateField('decisionFramework', value)}
            className="grid grid-cols-1 md:grid-cols-2 gap-4"
          >
            {frameworks.map((framework) => (
              <div key={framework.id}>
                <RadioGroupItem
                  value={framework.id}
                  id={framework.id}
                  className="peer sr-only"
                />
                <Label
                  htmlFor={framework.id}
                  className="flex flex-col items-start p-4 border rounded-lg cursor-pointer transition-all hover:bg-muted peer-data-[state=checked]:border-primary peer-data-[state=checked]:bg-primary/5"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <framework.icon className="h-5 w-5 text-primary" />
                    <span className="font-semibold">{framework.label}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">{framework.description}</span>
                </Label>
              </div>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      {/* Cognitive Heuristics */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Cognitive Heuristics</CardTitle>
            <button
              onClick={() => setShowHeuristicHelp(!showHeuristicHelp)}
              className="text-muted-foreground hover:text-foreground"
            >
              <HelpCircle className="h-5 w-5" />
            </button>
          </div>
          {showHeuristicHelp && (
            <p className="text-sm text-muted-foreground mt-2">
              Heuristics are mental shortcuts you use when evaluating situations. 
              Select the ones that match how you naturally think.
            </p>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-3">
            {defaultHeuristics.map((heuristic) => (
              <div
                key={heuristic.id}
                className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-muted/50 transition-colors"
              >
                <Checkbox
                  id={heuristic.id}
                  checked={data.heuristics?.includes(heuristic.id)}
                  onCheckedChange={() => toggleHeuristic(heuristic.id)}
                />
                <div className="flex-1">
                  <Label
                    htmlFor={heuristic.id}
                    className="font-medium cursor-pointer"
                  >
                    {heuristic.label}
                  </Label>
                  <p className="text-sm text-muted-foreground">{heuristic.desc}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-2 pt-4 border-t">
            <Label htmlFor="custom-heuristics">Additional Heuristics (Optional)</Label>
            <Textarea
              id="custom-heuristics"
              placeholder="Describe any other mental models or heuristics you use..."
              value={data.customHeuristics || ''}
              onChange={(e) => updateField('customHeuristics', e.target.value)}
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      {/* Clarifying Behavior */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">When Information is Insufficient</CardTitle>
        </CardHeader>
        <CardContent>
          <RadioGroup
            value={data.clarifyingBehavior}
            onValueChange={(value: 'ask' | 'infer') => updateField('clarifyingBehavior', value)}
            className="space-y-3"
          >
            <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-muted/50">
              <RadioGroupItem value="ask" id="clarify-ask" />
              <div className="flex-1">
                <Label htmlFor="clarify-ask" className="font-medium cursor-pointer">
                  Ask Clarifying Questions
                </Label>
                <p className="text-sm text-muted-foreground">
                  When uncertain, ask the user for more information before giving an assessment.
                </p>
              </div>
            </div>
            <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-muted/50">
              <RadioGroupItem value="infer" id="clarify-infer" />
              <div className="flex-1">
                <Label htmlFor="clarify-infer" className="font-medium cursor-pointer">
                  Infer Best Effort
                </Label>
                <p className="text-sm text-muted-foreground">
                  Make reasonable assumptions and proceed with evaluation, disclosing uncertainty.
                </p>
              </div>
            </div>
          </RadioGroup>
        </CardContent>
      </Card>

      {/* Evidence Standards */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Evidence Standards</CardTitle>
          <p className="text-sm text-muted-foreground">
            What makes evidence credible to you?
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3">
            {evidenceStandards.map((standard) => (
              <div
                key={standard.id}
                className="flex items-center space-x-2"
              >
                <Checkbox
                  id={standard.id}
                  checked={data.evidenceStandards?.includes(standard.id)}
                  onCheckedChange={() => toggleEvidenceStandard(standard.id)}
                />
                <Label htmlFor={standard.id} className="text-sm cursor-pointer">
                  {standard.label}
                </Label>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
