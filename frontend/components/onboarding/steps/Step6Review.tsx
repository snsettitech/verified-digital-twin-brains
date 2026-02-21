'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/Card';

interface ReviewData {
  twinName: string;
  tagline: string;
  specialization: string;
  expertise: string[];
  decisionFramework: string;
  heuristics: string[];
  clarifyingBehavior: string;
  prioritizedValues: { name: string; description: string }[];
  personality: {
    tone: string;
    responseLength: string;
    firstPerson: boolean;
  };
  memoryCount: number;
}

interface Step6Props {
  data: ReviewData;
  onTestChat: () => void;
  onEditStep: (step: number) => void;
  onLaunch: () => void;
  isLaunching: boolean;
}

export function Step6Review({ data, onTestChat, onEditStep, onLaunch, isLaunching }: Step6Props) {
  const [activeTab, setActiveTab] = useState<'summary' | 'test'>('summary');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    identity: true,
    thinking: true,
    values: true,
    communication: true,
    memory: true,
  });

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const sections = [
    {
      id: 'identity',
      title: 'Layer 1: Identity Frame',
      icon: '👤',
      content: (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Name</span>
            <span className="font-medium text-white">{data.twinName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Tagline</span>
            <span className="font-medium text-white">{data.tagline || 'Not set'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Specialization</span>
            <span className="font-medium text-white capitalize">{data.specialization}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Expertise</span>
            <span className="font-medium text-white">{data.expertise.length} domains</span>
          </div>
        </div>
      ),
    },
    {
      id: 'thinking',
      title: 'Layer 2: Thinking Style',
      icon: '🧠',
      content: (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Decision Framework</span>
            <span className="font-medium text-white capitalize">{data.decisionFramework.replace('_', ' ')}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Heuristics</span>
            <span className="font-medium text-white">{data.heuristics.length} selected</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">When Uncertain</span>
            <span className="font-medium text-white capitalize">{data.clarifyingBehavior === 'ask' ? 'Ask Questions' : 'Infer Best Effort'}</span>
          </div>
        </div>
      ),
    },
    {
      id: 'values',
      title: 'Layer 3: Value Hierarchy',
      icon: '❤️',
      content: (
        <div className="space-y-2 text-sm">
          <div className="text-slate-400 mb-2">Top 3 Priorities:</div>
          <div className="space-y-1">
            {data.prioritizedValues.slice(0, 3).map((value, i) => (
              <div key={value.name} className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-indigo-500/20 flex items-center justify-center text-xs font-medium text-indigo-400">
                  {i + 1}
                </span>
                <span className="text-white">{value.name}</span>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      id: 'communication',
      title: 'Layer 4: Communication',
      icon: '💬',
      content: (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Tone</span>
            <span className="font-medium text-white capitalize">{data.personality.tone}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Response Length</span>
            <span className="font-medium text-white capitalize">{data.personality.responseLength}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Perspective</span>
            <span className="font-medium text-white">{data.personality.firstPerson ? 'First Person (I/me)' : 'Third Person (by name)'}</span>
          </div>
        </div>
      ),
    },
    {
      id: 'memory',
      title: 'Layer 5: Memory Anchors',
      icon: '📚',
      content: (
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Memory Anchors</span>
            <span className="font-medium text-white">{data.memoryCount} stored</span>
          </div>
          <p className="text-slate-400">
            These experiences and lessons will inform contextual advice.
          </p>
        </div>
      ),
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
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-500/20 rounded-full mb-4">
          <span className="text-xl">✨</span>
          <span className="text-sm font-medium text-indigo-400">5-Layer Persona Complete</span>
        </div>
        <h2 className="text-2xl font-bold mb-2">Review Your Digital Twin</h2>
        <p className="text-slate-400">
          Preview how your twin will respond and make adjustments before launching.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('summary')}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
            activeTab === 'summary'
              ? 'bg-indigo-600 text-white'
              : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
          }`}
        >
          Summary
        </button>
        <button
          onClick={() => setActiveTab('test')}
          className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
            activeTab === 'test'
              ? 'bg-indigo-600 text-white'
              : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
          }`}
        >
          Test Sandbox
        </button>
      </div>

      {activeTab === 'summary' ? (
        <div className="space-y-4">
          {/* Persona Completeness Badge */}
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4 flex items-start gap-3">
            <span className="text-green-400 text-xl">✓</span>
            <div>
              <p className="font-medium text-green-400">Persona Spec v2 Ready</p>
              <p className="text-sm text-slate-400">
                Your 5-Layer Persona includes structured Identity, Thinking Style, Values, 
                Communication Patterns, and Memory Anchors.
              </p>
            </div>
          </div>

          {/* Collapsible Sections */}
          {sections.map((section, idx) => (
            <Card key={section.id} className="overflow-hidden">
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full p-4 flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">{section.icon}</span>
                  <span className="font-semibold text-white">{section.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onEditStep(idx + 1);
                    }}
                    className="text-sm text-indigo-400 hover:text-indigo-300 px-2 py-1"
                  >
                    Edit
                  </button>
                  <span className="text-slate-400">
                    {expandedSections[section.id] ? '▼' : '▶'}
                  </span>
                </div>
              </button>
              {expandedSections[section.id] && (
                <div className="px-4 pb-4">{section.content}</div>
              )}
            </Card>
          ))}

          {/* Launch Button */}
          <div className="pt-4">
            <button
              onClick={onLaunch}
              disabled={isLaunching}
              className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-all flex items-center justify-center gap-2"
            >
              {isLaunching ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating Your Twin...
                </>
              ) : (
                <>
                  <span>✨</span>
                  Launch Digital Twin
                </>
              )}
            </button>
            <p className="text-center text-sm text-slate-400 mt-2">
              Your twin will be created with 5-Layer Persona Spec v2 and immediately available for chat.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <span className="text-xl">💬</span>
              Test Sandbox
            </h3>
            <p className="text-sm text-slate-400 mb-4">
              Send a test message to see how your twin responds with the current persona.
            </p>
            <div className="bg-slate-800 rounded-lg p-4 space-y-4">
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-white text-sm font-medium">
                  U
                </div>
                <div className="flex-1 bg-slate-700 rounded-lg p-3">
                  <p className="text-sm text-white">What do you think of this startup idea: AI-powered personal finance assistant for Gen Z?</p>
                </div>
              </div>
              
              <div className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-sm font-medium">
                  {data.twinName.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 bg-indigo-500/20 rounded-lg p-3">
                  <div className="space-y-2">
                    <p className="text-sm text-slate-400 italic">
                      [Your twin would respond here based on your persona settings]
                    </p>
                    <div className="flex flex-wrap gap-2 pt-2">
                      <span className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-300">
                        Framework: {data.decisionFramework.replace('_', ' ')}
                      </span>
                      <span className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-300">
                        Tone: {data.personality.tone}
                      </span>
                      <span className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-300">
                        Priority: {data.prioritizedValues[0]?.name || 'Quality'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <button
              onClick={onTestChat}
              className="w-full mt-4 py-3 border border-slate-600 hover:bg-slate-800 text-white rounded-lg transition-colors"
            >
              Open Full Test Chat
            </button>
          </Card>

          {/* What's Included */}
          <Card className="p-6 bg-slate-800/30">
            <h3 className="text-base font-semibold mb-4">What's Different with 5-Layer Persona?</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span className="text-slate-300"><strong>Structured Scoring:</strong> Responses include 1-5 dimension scores with reasoning</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span className="text-slate-300"><strong>Value-Aware:</strong> Tradeoffs resolved using your value hierarchy</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span className="text-slate-300"><strong>Safety Boundaries:</strong> Automatic refusal for investment/legal/medical advice</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span className="text-slate-300"><strong>Memory Context:</strong> References your experiences in advice</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-green-400">✓</span>
                <span className="text-slate-300"><strong>Explainable:</strong> Every decision shows which heuristics and values were used</span>
              </div>
            </div>
          </Card>

          <div className="flex items-start gap-3 p-4 border border-amber-500/30 bg-amber-500/10 rounded-lg">
            <span className="text-amber-400 text-xl">⚠️</span>
            <div className="text-sm">
              <p className="font-medium text-amber-400">Legacy Twins</p>
              <p className="text-slate-400">
                Existing twins continue using the legacy system. Only new twins created through 
                this onboarding flow get 5-Layer Persona v2.
              </p>
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
}
