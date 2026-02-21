'use client';

import { useState } from 'react';

import { Card } from '@/components/ui/Card';

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
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 3: Values & Priorities</h2>
        <p className="text-slate-400">
          Drag to rank what matters most to you. The order determines priority when values conflict.
        </p>
      </div>

      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <span className="text-xl">❤️</span>
              Your Value Hierarchy
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              Ranked by priority (1st = most important)
            </p>
          </div>
          <button
            onClick={resetToDefaults}
            className="px-3 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
          >
            Reset to Defaults
          </button>
        </div>
        
        <div className="space-y-3">
          {values.map((value, index) => (
            <div
              key={value.id}
              className="flex items-center gap-3 p-4 border border-slate-700 rounded-lg bg-slate-800/50"
            >
              {/* Rank Number */}
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center font-semibold text-sm text-indigo-400">
                {index + 1}
              </div>

              {/* Value Content */}
              <div className="flex-1 min-w-0">
                <h4 className="font-medium text-white truncate">{value.name}</h4>
                <p className="text-sm text-slate-400 truncate">{value.description}</p>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1">
                <button
                  className="p-2 hover:bg-slate-700 rounded-lg disabled:opacity-30 transition-colors"
                  disabled={index === 0}
                  onClick={() => moveValue(index, 'up')}
                >
                  <span className="text-slate-400">↑</span>
                </button>
                <button
                  className="p-2 hover:bg-slate-700 rounded-lg disabled:opacity-30 transition-colors"
                  disabled={index === values.length - 1}
                  onClick={() => moveValue(index, 'down')}
                >
                  <span className="text-slate-400">↓</span>
                </button>
                <button
                  className="p-2 hover:bg-red-500/20 rounded-lg text-red-400 transition-colors"
                  onClick={() => removeValue(index)}
                >
                  <span>🗑️</span>
                </button>
              </div>
            </div>
          ))}

          {/* Add New Value */}
          {showAddForm ? (
            <div
              className="p-4 border border-slate-700 rounded-lg bg-slate-800/50 space-y-3"
            >
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">Value Name</label>
                <input
                  type="text"
                  value={newValueName}
                  onChange={(e) => setNewValueName(e.target.value)}
                  placeholder="e.g., Customer Obsession"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">Description</label>
                <input
                  type="text"
                  value={newValueDesc}
                  onChange={(e) => setNewValueDesc(e.target.value)}
                  placeholder="Briefly describe what this value means to you..."
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={addValue}
                  disabled={!newValueName.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg transition-colors"
                >
                  Add Value
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowAddForm(true)}
              className="w-full py-3 border-2 border-dashed border-slate-700 rounded-lg text-slate-400 hover:border-slate-500 hover:text-slate-300 transition-colors"
            >
              + Add Custom Value
            </button>
          )}
        </div>
      </Card>

      {/* Tradeoff Notes */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Value Tradeoff Notes</h3>
        <p className="text-sm text-slate-400 mb-4">
          When values conflict, how do you typically decide?
        </p>
        <textarea
          placeholder="e.g., 'Quality usually wins over speed for customer-facing work, but speed matters more for internal tools...'"
          value={data.tradeoffNotes || ''}
          onChange={(e) => onChange({ ...data, tradeoffNotes: e.target.value })}
          rows={4}
          className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
        />
      </Card>

      {/* Help Text */}
      <div className="bg-slate-800/50 p-4 rounded-lg text-sm text-slate-400 border border-slate-700">
        <p className="font-medium text-white mb-2">Why this matters:</p>
        <p>
          Your value hierarchy guides how your digital twin evaluates situations and makes 
          recommendations. When facing tradeoffs (e.g., quality vs. speed), it will prioritize 
          based on your ranked values. This is Layer 3 of your persona.
        </p>
      </div>
    </div>
  );
}
