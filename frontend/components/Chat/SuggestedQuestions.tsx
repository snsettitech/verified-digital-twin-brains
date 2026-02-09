'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Question {
  question: string;
  count: number;
  avg_confidence: number;
}

interface SuggestedQuestionsProps {
  twinId: string;
  onSelect: (question: string) => void;
  disabled?: boolean;
}

// Default fallback questions when no data available
const DEFAULT_QUESTIONS = [
  'What can you help me with?',
  'Tell me about yourself',
  'What topics do you know about?',
  'How do you work?',
];

// Onboarding questions for new twins
const ONBOARDING_QUESTIONS = [
  "What's your main area of expertise?",
  'How would you describe your approach?',
  'What makes you different?',
  'What should I know about you?',
];

export default function SuggestedQuestions({ twinId, onSelect, disabled }: SuggestedQuestionsProps) {
  const [questions, setQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [usingDefaults, setUsingDefaults] = useState(false);

  const supabase = getSupabaseClient();

  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  }, [supabase]);

  const fetchQuestions = useCallback(async () => {
    if (!twinId) {
      setQuestions(ONBOARDING_QUESTIONS);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = await getAuthToken();
      
      // Try to fetch top questions from API
      const response = await fetch(`${API_BASE_URL}/metrics/top-questions/${twinId}?limit=5`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });

      if (response.ok) {
        const data: Question[] = await response.json();
        
        if (data && data.length > 0) {
          // Use real questions from API
          setQuestions(data.map(q => q.question));
          setUsingDefaults(false);
        } else {
          // No questions yet, use defaults
          setQuestions(DEFAULT_QUESTIONS);
          setUsingDefaults(true);
        }
      } else if (response.status === 404) {
        // API not available, use defaults
        setQuestions(DEFAULT_QUESTIONS);
        setUsingDefaults(true);
      } else {
        throw new Error(`API error: ${response.status}`);
      }
    } catch (err) {
      console.error('Failed to fetch suggested questions:', err);
      setError('Failed to load suggestions');
      setQuestions(DEFAULT_QUESTIONS);
      setUsingDefaults(true);
    } finally {
      setLoading(false);
    }
  }, [twinId, getAuthToken]);

  useEffect(() => {
    fetchQuestions();
  }, [fetchQuestions]);

  if (loading) {
    return (
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="flex-shrink-0 h-9 w-40 bg-slate-100 rounded-full animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (questions.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      {/* Label */}
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">
        {usingDefaults ? 'Suggested questions' : 'Popular questions'}
      </p>
      
      {/* Questions */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide -mx-1 px-1">
        {questions.map((question, index) => (
          <button
            key={index}
            onClick={() => !disabled && onSelect(question)}
            disabled={disabled}
            className={`flex-shrink-0 px-4 py-2 bg-white border border-slate-200 rounded-full text-sm text-slate-700 
              whitespace-nowrap transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1
              ${disabled 
                ? 'opacity-50 cursor-not-allowed' 
                : 'hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 hover:shadow-sm cursor-pointer'
              }`}
            title={question}
          >
            {question.length > 40 ? question.slice(0, 40) + '...' : question}
          </button>
        ))}
      </div>
      
      {/* Error indicator (subtle) */}
      {error && usingDefaults && (
        <p className="text-xs text-slate-400 italic">
          Showing default suggestions
        </p>
      )}
    </div>
  );
}

// Horizontal scrollbar hide utility
const scrollbarHideStyles = `
  .scrollbar-hide::-webkit-scrollbar {
    display: none;
  }
  .scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
`;

// Inject styles if not already present
if (typeof document !== 'undefined') {
  const styleId = 'suggested-questions-styles';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = scrollbarHideStyles;
    document.head.appendChild(style);
  }
}
