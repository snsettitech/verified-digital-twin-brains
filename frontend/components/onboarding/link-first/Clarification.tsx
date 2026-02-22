'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';

interface Question {
  target_item_id: string;
  question: string;
  current_confidence: number;
  purpose: string;
}

interface ClarificationProps {
  twinId: string | null;
  onComplete: () => void;
}

export function Clarification({ twinId, onComplete }: ClarificationProps) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!twinId) return;

    const fetchQuestions = async () => {
      try {
        const response = await fetch(`/api/persona/link-compile/twins/${twinId}/clarification-questions`);
        if (!response.ok) throw new Error('Failed to fetch questions');
        
        const data = await response.json();
        setQuestions(data.questions || []);
      } catch (e) {
        console.error('Failed to load questions:', e);
      } finally {
        setLoading(false);
      }
    };

    fetchQuestions();
  }, [twinId]);

  const handleAnswerChange = (questionId: string, value: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: value }));
  };

  const handleSubmit = async () => {
    if (!twinId) return;
    
    setSubmitting(true);
    
    try {
      // Submit each answer
      for (const question of questions) {
        if (answers[question.target_item_id]?.trim()) {
          await fetch(`/api/persona/link-compile/twins/${twinId}/clarification-answers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              question_id: question.target_item_id,
              question: question,
              answer: answers[question.target_item_id],
            }),
          });
        }
      }

      // Transition to persona_built
      await fetch(`/api/twins/${twinId}/transition/persona-built`, {
        method: 'POST',
      });

      onComplete();
    } catch (e) {
      console.error('Failed to submit answers:', e);
      alert('Failed to save answers. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = questions.every(q => 
    answers[q.target_item_id]?.trim().length > 0
  );

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-400">Generating clarification questions...</p>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="space-y-6">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold mb-2 text-white">Clarification Complete</h2>
          <p className="text-slate-400">No clarification needed. Your claims are sufficient!</p>
        </div>
        <button
          onClick={onComplete}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-semibold"
        >
          Continue
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2 text-white">Clarification Questions</h2>
        <p className="text-slate-400">
          Help us understand your preferences better. These answers will improve your persona.
        </p>
      </div>

      <div className="space-y-4">
        {questions.map((q, idx) => (
          <Card key={q.target_item_id} className="p-6 bg-slate-900 border-slate-700">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 rounded-full bg-indigo-500/20 flex items-center justify-center text-indigo-400 font-semibold flex-shrink-0">
                {idx + 1}
              </div>
              <div className="flex-1">
                <p className="text-white font-medium mb-3">{q.question}</p>
                <p className="text-sm text-slate-500 mb-3">
                  Current confidence: {Math.round(q.current_confidence * 100)}%
                </p>
                <textarea
                  value={answers[q.target_item_id] || ''}
                  onChange={(e) => handleAnswerChange(q.target_item_id, e.target.value)}
                  placeholder="Your answer..."
                  rows={3}
                  className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        disabled={!canSubmit || submitting}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold transition-colors flex items-center justify-center gap-2"
      >
        {submitting ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Saving...
          </>
        ) : (
          'Complete & Build Persona'
        )}
      </button>
    </div>
  );
}
