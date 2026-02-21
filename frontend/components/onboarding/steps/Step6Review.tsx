'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Check, 
  ChevronDown, 
  ChevronUp, 
  MessageSquare, 
  User, 
  Brain, 
  Heart, 
  MessageCircle, 
  Archive,
  AlertTriangle,
  Sparkles
} from 'lucide-react';

interface ReviewData {
  // Identity (Step 1)
  twinName: string;
  tagline: string;
  specialization: string;
  expertise: string[];
  // Thinking (Step 2)
  decisionFramework: string;
  heuristics: string[];
  clarifyingBehavior: string;
  // Values (Step 3)
  prioritizedValues: { name: string; description: string }[];
  // Communication (Step 4)
  personality: {
    tone: string;
    responseLength: string;
    firstPerson: boolean;
  };
  // Memory (Step 5)
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
      icon: User,
      color: 'text-blue-500',
      content: (
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Name</span>
            <span className="font-medium">{data.twinName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Tagline</span>
            <span className="font-medium">{data.tagline || 'Not set'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Specialization</span>
            <span className="font-medium capitalize">{data.specialization}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Expertise</span>
            <span className="font-medium">{data.expertise.length} domains</span>
          </div>
        </div>
      ),
    },
    {
      id: 'thinking',
      title: 'Layer 2: Thinking Style',
      icon: Brain,
      color: 'text-purple-500',
      content: (
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Decision Framework</span>
            <span className="font-medium capitalize">{data.decisionFramework.replace('_', ' ')}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Heuristics</span>
            <span className="font-medium">{data.heuristics.length} selected</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">When Uncertain</span>
            <span className="font-medium capitalize">{data.clarifyingBehavior === 'ask' ? 'Ask Questions' : 'Infer Best Effort'}</span>
          </div>
        </div>
      ),
    },
    {
      id: 'values',
      title: 'Layer 3: Value Hierarchy',
      icon: Heart,
      color: 'text-rose-500',
      content: (
        <div className="space-y-2">
          <div className="text-sm text-muted-foreground mb-2">Top 3 Priorities:</div>
          <div className="space-y-1">
            {data.prioritizedValues.slice(0, 3).map((value, i) => (
              <div key={value.name} className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium">
                  {i + 1}
                </span>
                <span>{value.name}</span>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      id: 'communication',
      title: 'Layer 4: Communication',
      icon: MessageCircle,
      color: 'text-green-500',
      content: (
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Tone</span>
            <span className="font-medium capitalize">{data.personality.tone}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Response Length</span>
            <span className="font-medium capitalize">{data.personality.responseLength}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Perspective</span>
            <span className="font-medium">{data.personality.firstPerson ? 'First Person (I/me)' : 'Third Person (by name)'}</span>
          </div>
        </div>
      ),
    },
    {
      id: 'memory',
      title: 'Layer 5: Memory Anchors',
      icon: Archive,
      color: 'text-amber-500',
      content: (
        <div className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Memory Anchors</span>
            <span className="font-medium">{data.memoryCount} stored</span>
          </div>
          <p className="text-sm text-muted-foreground">
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
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 rounded-full mb-4">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-primary">5-Layer Persona Complete</span>
        </div>
        <h2 className="text-2xl font-bold mb-2">Review Your Digital Twin</h2>
        <p className="text-muted-foreground">
          Preview how your twin will respond and make adjustments before launching.
        </p>
      </div>

      <Tabs defaultValue="summary" className="w-full">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="test">Test Sandbox</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          {/* Persona Completeness Badge */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-start gap-3">
            <Check className="h-5 w-5 text-green-600 mt-0.5" />
            <div>
              <p className="font-medium text-green-900">Persona Spec v2 Ready</p>
              <p className="text-sm text-green-700">
                Your 5-Layer Persona includes structured Identity, Thinking Style, Values, 
                Communication Patterns, and Memory Anchors. This enables structured scoring 
                and explainable decisions.
              </p>
            </div>
          </div>

          {/* Collapsible Sections */}
          {sections.map((section) => (
            <Card key={section.id} className="overflow-hidden">
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full"
              >
                <CardHeader className="flex flex-row items-center justify-between py-4">
                  <div className="flex items-center gap-3">
                    <section.icon className={`h-5 w-5 ${section.color}`} />
                    <CardTitle className="text-base">{section.title}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditStep(sections.indexOf(section) + 1);
                      }}
                    >
                      Edit
                    </Button>
                    {expandedSections[section.id] ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </CardHeader>
              </button>
              {expandedSections[section.id] && (
                <CardContent className="pt-0">{section.content}</CardContent>
              )}
            </Card>
          ))}

          {/* Launch Button */}
          <div className="pt-4">
            <Button
              size="lg"
              className="w-full"
              onClick={onLaunch}
              disabled={isLaunching}
            >
              {isLaunching ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Creating Your Twin...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Launch Digital Twin
                </>
              )}
            </Button>
            <p className="text-center text-sm text-muted-foreground mt-2">
              Your twin will be created with 5-Layer Persona Spec v2 and immediately available for chat.
            </p>
          </div>
        </TabsContent>

        <TabsContent value="test" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <MessageSquare className="h-5 w-5" />
                Test Sandbox
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Send a test message to see how your twin responds with the current persona.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-muted rounded-lg p-4 space-y-4">
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-medium">
                    U
                  </div>
                  <div className="flex-1 bg-background rounded-lg p-3">
                    <p className="text-sm">What do you think of this startup idea: AI-powered personal finance assistant for Gen Z?</p>
                  </div>
                </div>
                
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center text-secondary-foreground text-sm font-medium">
                    {data.twinName.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 bg-secondary/50 rounded-lg p-3">
                    <div className="space-y-2">
                      <p className="text-sm italic text-muted-foreground">
                        [Your twin would respond here based on your persona settings]
                      </p>
                      <div className="flex flex-wrap gap-2 pt-2">
                        <Badge variant="outline" className="text-xs">
                          Framework: {data.decisionFramework.replace('_', ' ')}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          Tone: {data.personality.tone}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          Priority: {data.prioritizedValues[0]?.name || 'Quality'}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <Button variant="outline" className="w-full" onClick={onTestChat}>
                <MessageSquare className="mr-2 h-4 w-4" />
                Open Full Test Chat
              </Button>
            </CardContent>
          </Card>

          {/* What's Included */}
          <Card className="bg-muted/30">
            <CardHeader>
              <CardTitle className="text-base">What's Different with 5-Layer Persona?</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-green-500 mt-0.5" />
                <span><strong>Structured Scoring:</strong> Responses include 1-5 dimension scores with reasoning</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-green-500 mt-0.5" />
                <span><strong>Value-Aware:</strong> Tradeoffs resolved using your value hierarchy</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-green-500 mt-0.5" />
                <span><strong>Safety Boundaries:</strong> Automatic refusal for investment/legal/medical advice</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-green-500 mt-0.5" />
                <span><strong>Memory Context:</strong> References your experiences in advice</span>
              </div>
              <div className="flex items-start gap-2">
                <Check className="h-4 w-4 text-green-500 mt-0.5" />
                <span><strong>Explainable:</strong> Every decision shows which heuristics and values were used</span>
              </div>
            </CardContent>
          </Card>

          <div className="flex items-start gap-3 p-4 border border-amber-200 bg-amber-50 rounded-lg">
            <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-amber-900">Legacy Twins</p>
              <p className="text-amber-700">
                Existing twins continue using the legacy system. Only new twins created through 
                this onboarding flow get 5-Layer Persona v2.
              </p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </motion.div>
  );
}
