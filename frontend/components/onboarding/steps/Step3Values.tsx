'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ArrowUp, ArrowDown, GripVertical, Heart, Plus, Trash2 } from 'lucide-react';

interface ValueItem {
  id: string;
  name: string;
  description: string;
}

interface ValuesData {
  prioritizedValues: ValueItem[];
  tradeoffNotes: string;
}

interface Step3Props {
  data: ValuesData;
  onChange: (data: ValuesData) => void;
  specialization: string;
}

const defaultValues: Record<string, ValueItem[]> = {
  founder: [
    { id: 'team_quality', name: 'Team Quality', description: 'Strong founding team with relevant experience' },
    { id: 'market_size', name: 'Market Size', description: 'Large addressable market with growth potential' },
    { id: 'traction', name: 'Traction', description: 'Evidence of product-market fit' },
    { id: 'defensibility', name: 'Defensibility', description: 'Sustainable competitive advantage' },
    { id: 'speed', name: 'Speed of Execution', description: 'Velocity of execution and iteration' },
  ],
  technical: [
    { id: 'technical_excellence', name: 'Technical Excellence', description: 'Sound architecture and implementation' },
    { id: 'scalability', name: 'Scalability', description: 'Ability to handle growth' },
    { id: 'security', name: 'Security', description: 'Security and privacy considerations' },
    { id: 'maintainability', name: 'Maintainability', description: 'Code quality and documentation' },
    { id: 'innovation', name: 'Innovation', description: 'Novel approaches and defensible tech' },
  ],
  creator: [
    { id: 'authenticity', name: 'Authenticity', description: 'Genuine voice and honest communication' },
    { id: 'audience_value', name: 'Audience Value', description: 'Content that serves the audience' },
    { id: 'consistency', name: 'Consistency', description: 'Regular output and reliability' },
    { id: 'quality', name: 'Quality', description: 'High production and thought quality' },
    { id: 'growth', name: 'Growth', description: 'Continuous improvement and learning' },
  ],
  vanilla: [
    { id: 'quality', name: 'Quality', description: 'High standards in work' },
    { id: 'clarity', name: 'Clarity', description: 'Clear and understandable communication' },
    { id: 'helpfulness', name: 'Helpfulness', description: 'Actually solving the problem' },
    { id: 'honesty', name: 'Honesty', description: 'Truthful about limitations' },
    { id: 'efficiency', name: 'Efficiency', description: 'Respecting time' },
  ],
};

export function Step3Values({ data, onChange, specialization }: Step3Props) {
  const [newValueName, setNewValueName] = useState('');
  const [newValueDesc, setNewValueDesc] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Initialize with defaults if empty
  const values = data.prioritizedValues.length > 0
    ? data.prioritizedValues
    : defaultValues[specialization] || defaultValues.vanilla;

  const updateValues = (newValues: ValueItem[]) => {
    onChange({ ...data, prioritizedValues: newValues });
  };

  const moveValue = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === values.length - 1) return;

    const newValues = [...values];
    const swapIndex = direction === 'up' ? index - 1 : index + 1;
    [newValues[index], newValues[swapIndex]] = [newValues[swapIndex], newValues[index]];
    updateValues(newValues);
  };

  const removeValue = (index: number) => {
    const newValues = values.filter((_, i) => i !== index);
    updateValues(newValues);
  };

  const addValue = () => {
    if (!newValueName.trim()) return;
    
    const newValue: ValueItem = {
      id: `custom_${Date.now()}`,
      name: newValueName.trim(),
      description: newValueDesc.trim(),
    };
    
    updateValues([...values, newValue]);
    setNewValueName('');
    setNewValueDesc('');
    setShowAddForm(false);
  };

  const resetToDefaults = () => {
    const defaults = defaultValues[specialization] || defaultValues.vanilla;
    updateValues([...defaults]);
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 3: Values & Priorities</h2>
        <p className="text-muted-foreground">
          Drag to rank what matters most to you. The order determines priority when values conflict.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Heart className="h-5 w-5 text-rose-500" />
              Your Value Hierarchy
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Ranked by priority (1st = most important)
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={resetToDefaults}>
            Reset to Defaults
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {values.map((value, index) => (
            <motion.div
              key={value.id}
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-3 p-4 border rounded-lg bg-card hover:shadow-sm transition-shadow"
            >
              {/* Rank Number */}
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-semibold text-sm">
                {index + 1}
              </div>

              {/* Drag Handle */}
              <div className="flex-shrink-0 text-muted-foreground">
                <GripVertical className="h-5 w-5" />
              </div>

              {/* Value Content */}
              <div className="flex-1 min-w-0">
                <h4 className="font-medium truncate">{value.name}</h4>
                <p className="text-sm text-muted-foreground truncate">{value.description}</p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  disabled={index === 0}
                  onClick={() => moveValue(index, 'up')}
                >
                  <ArrowUp className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  disabled={index === values.length - 1}
                  onClick={() => moveValue(index, 'down')}
                >
                  <ArrowDown className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => removeValue(index)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </motion.div>
          ))}

          {/* Add New Value */}
          {showAddForm ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="p-4 border rounded-lg bg-muted/50 space-y-3"
            >
              <div className="space-y-2">
                <Label htmlFor="new-value-name">Value Name</Label>
                <input
                  id="new-value-name"
                  type="text"
                  value={newValueName}
                  onChange={(e) => setNewValueName(e.target.value)}
                  placeholder="e.g., Customer Obsession"
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-value-desc">Description</Label>
                <input
                  id="new-value-desc"
                  type="text"
                  value={newValueDesc}
                  onChange={(e) => setNewValueDesc(e.target.value)}
                  placeholder="Briefly describe what this value means to you..."
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={addValue} disabled={!newValueName.trim()}>
                  Add Value
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setShowAddForm(false)}>
                  Cancel
                </Button>
              </div>
            </motion.div>
          ) : (
            <Button
              variant="outline"
              className="w-full"
              onClick={() => setShowAddForm(true)}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Custom Value
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Tradeoff Notes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Value Tradeoff Notes</CardTitle>
          <p className="text-sm text-muted-foreground">
            When values conflict, how do you typically decide?
          </p>
        </CardHeader>
        <CardContent>
          <Textarea
            placeholder="e.g., 'Quality usually wins over speed for customer-facing work, but speed matters more for internal tools...'"
            value={data.tradeoffNotes || ''}
            onChange={(e) => onChange({ ...data, tradeoffNotes: e.target.value })}
            rows={4}
          />
        </CardContent>
      </Card>

      {/* Help Text */}
      <div className="bg-muted/50 p-4 rounded-lg text-sm text-muted-foreground">
        <p className="font-medium mb-2">Why this matters:</p>
        <p>
          Your value hierarchy guides how your digital twin evaluates situations and makes 
          recommendations. When facing tradeoffs (e.g., quality vs. speed), it will prioritize 
          based on your ranked values. This is Layer 3 of your persona.
        </p>
      </div>
    </motion.div>
  );
}
