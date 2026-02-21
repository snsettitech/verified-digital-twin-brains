'use client';

import { useState } from 'react';
// Animations removed for production deployment
import { Card } from '@/components/ui/Card';

interface MemoryAnchor {
  id: string;
  type: 'experience' | 'lesson' | 'pattern';
  content: string;
  context: string;
  tags: string[];
}

interface MemoryData {
  experiences: MemoryAnchor[];
  lessons: MemoryAnchor[];
  patterns: MemoryAnchor[];
}

interface Step5Props {
  data: MemoryData;
  onChange: (data: MemoryData) => void;
}

export function Step5Memory({ data, onChange }: Step5Props) {
  const [activeTab, setActiveTab] = useState<'experiences' | 'lessons' | 'patterns'>('experiences');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newContent, setNewContent] = useState('');
  const [newContext, setNewContext] = useState('');
  const [newTags, setNewTags] = useState('');

  const updateSection = (section: keyof MemoryData, items: MemoryAnchor[]) => {
    onChange({ ...data, [section]: items });
  };

  const addItem = () => {
    if (!newContent.trim()) return;

    const newAnchor: MemoryAnchor = {
      id: `${activeTab}_${Date.now()}`,
      type: activeTab,
      content: newContent.trim(),
      context: newContext.trim(),
      tags: newTags.split(',').map((t) => t.trim()).filter(Boolean),
    };

    updateSection(activeTab, [...data[activeTab], newAnchor]);
    setNewContent('');
    setNewContext('');
    setNewTags('');
    setShowAddForm(false);
  };

  const removeItem = (section: keyof MemoryData, index: number) => {
    const items = data[section].filter((_, i) => i !== index);
    updateSection(section, items);
  };

  const tabs = [
    {
      id: 'experiences' as const,
      label: 'Key Experiences',
      icon: '🧠',
      description: 'Significant experiences that shaped your perspective',
    },
    {
      id: 'lessons' as const,
      label: 'Lessons Learned',
      icon: '💡',
      description: 'Principles and insights from your experience',
    },
    {
      id: 'patterns' as const,
      label: 'Recurring Patterns',
      icon: '🔀',
      description: 'Trends or patterns you have observed repeatedly',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2">Layer 5: Memory Anchors</h2>
        <p className="text-slate-400">
          Key experiences, lessons, and patterns that inform your judgment. These contextualize your advice.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              setShowAddForm(false);
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active Tab Content */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
          <span className="text-xl">{tabs.find((t) => t.id === activeTab)?.icon}</span>
          {tabs.find((t) => t.id === activeTab)?.label}
        </h3>
        <p className="text-sm text-slate-400 mb-4">
          {tabs.find((t) => t.id === activeTab)?.description}
        </p>
        
        <div className="space-y-4">
          {/* Existing Items */}
          {data[activeTab].length === 0 ? (
            <div className="text-center py-8 text-slate-400 border-2 border-dashed border-slate-700 rounded-lg">
              <p>No {tabs.find((t) => t.id === activeTab)?.label.toLowerCase()} added yet.</p>
              <p className="text-sm">Add memories to help your twin give contextualized advice.</p>
            </div>
          ) : (
            data[activeTab].map((item, index) => (
              <div
                key={item.id}
                className="p-4 border border-slate-700 rounded-lg bg-slate-800/30 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-white flex-1">{item.content}</p>
                  <button
                    className="text-red-400 hover:text-red-300 p-1"
                    onClick={() => removeItem(activeTab, index)}
                  >
                    🗑️
                  </button>
                </div>
                {item.context && (
                  <p className="text-sm text-slate-400">{item.context}</p>
                )}
                {item.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 bg-indigo-500/20 text-indigo-400 text-xs rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}

          {/* Add New Form */}
          {showAddForm ? (
            <div
              className="space-y-4 p-4 border border-slate-700 rounded-lg bg-slate-800/50"
            >
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">
                  {activeTab === 'experiences' && 'What happened?'}
                  {activeTab === 'lessons' && 'What did you learn?'}
                  {activeTab === 'patterns' && 'What pattern do you observe?'}
                </label>
                <textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder={
                    activeTab === 'experiences'
                      ? "e.g., Led a team of 20 through a major product pivot..."
                      : activeTab === 'lessons'
                      ? "e.g., Early customer validation saves months of wasted effort..."
                      : "e.g., Most successful pivots happen when teams listen to customer pain points..."
                  }
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">Context (Optional)</label>
                <input
                  type="text"
                  value={newContext}
                  onChange={(e) => setNewContext(e.target.value)}
                  placeholder="When is this most relevant?"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">Tags (Optional, comma-separated)</label>
                <input
                  type="text"
                  value={newTags}
                  onChange={(e) => setNewTags(e.target.value)}
                  placeholder="e.g., leadership, product, fundraising"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={addItem}
                  disabled={!newContent.trim()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg transition-colors"
                >
                  Add
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
              + Add {tabs.find((t) => t.id === activeTab)?.label.slice(0, -1)}
            </button>
          )}
        </div>
      </Card>

      {/* Summary Card */}
      <Card className="p-6 bg-slate-800/30">
        <h3 className="text-base font-semibold mb-4">Memory Summary</h3>
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-indigo-400">{data.experiences.length}</div>
            <div className="text-sm text-slate-400">Experiences</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-indigo-400">{data.lessons.length}</div>
            <div className="text-sm text-slate-400">Lessons</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-indigo-400">{data.patterns.length}</div>
            <div className="text-sm text-slate-400">Patterns</div>
          </div>
        </div>
      </Card>

      {/* Help Text */}
      <div className="bg-slate-800/50 p-4 rounded-lg text-sm text-slate-400 border border-slate-700">
        <p className="font-medium text-white mb-2">Why memory anchors matter:</p>
        <p>
          These memories give your digital twin context for advice. When evaluating a situation, 
          it can reference relevant experiences to provide more nuanced guidance. Think of these 
          as &quot;stories I often tell when advising people.&quot;
        </p>
      </div>
    </motion.div>
  );
}
