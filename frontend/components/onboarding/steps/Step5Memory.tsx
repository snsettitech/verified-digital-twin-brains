'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Brain, Lightbulb, Plus, Trash2 } from 'lucide-react';

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
      icon: Brain,
      description: 'Significant experiences that shaped your perspective',
    },
    {
      id: 'lessons' as const,
      label: 'Lessons Learned',
      icon: Lightbulb,
      description: 'Principles and insights from your experience',
    },
    {
      id: 'patterns' as const,
      label: 'Recurring Patterns',
      icon: () => (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 3v18M3 12h18M7.5 7.5l9 9M16.5 7.5l-9 9" />
        </svg>
      ),
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
        <p className="text-muted-foreground">
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
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted hover:bg-muted/80'
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active Tab Content */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            {(() => {
              const TabIcon = tabs.find((t) => t.id === activeTab)?.icon || Brain;
              return <TabIcon className="h-5 w-5" />;
            })()}
            {tabs.find((t) => t.id === activeTab)?.label}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {tabs.find((t) => t.id === activeTab)?.description}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Existing Items */}
          {data[activeTab].length === 0 ? (
            <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg">
              <p>No {tabs.find((t) => t.id === activeTab)?.label.toLowerCase()} added yet.</p>
              <p className="text-sm">Add memories to help your twin give contextualized advice.</p>
            </div>
          ) : (
            data[activeTab].map((item, index) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 border rounded-lg bg-muted/30 space-y-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium flex-1">{item.content}</p>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={() => removeItem(activeTab, index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
                {item.context && (
                  <p className="text-sm text-muted-foreground">{item.context}</p>
                )}
                {item.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-full"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </motion.div>
            ))
          )}

          {/* Add New Form */}
          {showAddForm ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="space-y-4 p-4 border rounded-lg bg-muted/50"
            >
              <div className="space-y-2">
                <Label>
                  {activeTab === 'experiences' && 'What happened?'}
                  {activeTab === 'lessons' && 'What did you learn?'}
                  {activeTab === 'patterns' && 'What pattern do you observe?'}
                </Label>
                <Textarea
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
                />
              </div>

              <div className="space-y-2">
                <Label>Context (Optional)</Label>
                <Input
                  value={newContext}
                  onChange={(e) => setNewContext(e.target.value)}
                  placeholder="When is this most relevant?"
                />
              </div>

              <div className="space-y-2">
                <Label>Tags (Optional, comma-separated)</Label>
                <Input
                  value={newTags}
                  onChange={(e) => setNewTags(e.target.value)}
                  placeholder="e.g., leadership, product, fundraising"
                />
              </div>

              <div className="flex gap-2">
                <Button onClick={addItem} disabled={!newContent.trim()}>
                  Add
                </Button>
                <Button variant="ghost" onClick={() => setShowAddForm(false)}>
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
              Add {tabs.find((t) => t.id === activeTab)?.label.slice(0, -1)}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Summary Card */}
      <Card className="bg-muted/30">
        <CardHeader>
          <CardTitle className="text-base">Memory Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-2xl font-bold text-primary">{data.experiences.length}</div>
              <div className="text-sm text-muted-foreground">Experiences</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-primary">{data.lessons.length}</div>
              <div className="text-sm text-muted-foreground">Lessons</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-primary">{data.patterns.length}</div>
              <div className="text-sm text-muted-foreground">Patterns</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Help Text */}
      <div className="bg-muted/50 p-4 rounded-lg text-sm text-muted-foreground">
        <p className="font-medium mb-2">Why memory anchors matter:</p>
        <p>
          These memories give your digital twin context for advice. When evaluating a situation, 
          it can reference relevant experiences to provide more nuanced guidance. Think of these 
          as "stories I often tell when advising people."
        </p>
      </div>
    </motion.div>
  );
}
