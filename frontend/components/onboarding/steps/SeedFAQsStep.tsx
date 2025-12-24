'use client';

import React from 'react';
import { WizardStep } from '../Wizard';

interface FAQPair {
    question: string;
    answer: string;
}

interface SeedFAQsStepProps {
    faqs: FAQPair[];
    onFaqsChange: (faqs: FAQPair[]) => void;
    expertiseDomains: string[];
}

const SUGGESTED_QUESTIONS: Record<string, string[]> = {
    'technology': [
        'What technology trends should companies focus on in 2025?',
        'How do you evaluate a startup\'s technical architecture?',
        'What are common mistakes in technology due diligence?',
    ],
    'ai-ml': [
        'How should companies approach AI adoption?',
        'What makes an AI startup investable?',
        'How do you evaluate an AI team\'s capabilities?',
    ],
    'finance': [
        'What financial metrics matter most for early-stage startups?',
        'How do you think about valuation in Series A?',
        'What are red flags in financial due diligence?',
    ],
    'default': [
        'What is your background and expertise?',
        'What makes you passionate about your field?',
        'What advice do you give most often?',
        'What\'s a common misconception in your industry?',
        'How can someone get started in your field?',
    ]
};

export function SeedFAQsStep({
    faqs,
    onFaqsChange,
    expertiseDomains
}: SeedFAQsStepProps) {
    // Get suggested questions based on domains
    const getSuggestions = () => {
        const suggestions: string[] = [];
        expertiseDomains.forEach(domain => {
            if (SUGGESTED_QUESTIONS[domain]) {
                suggestions.push(...SUGGESTED_QUESTIONS[domain]);
            }
        });
        if (suggestions.length < 5) {
            suggestions.push(...SUGGESTED_QUESTIONS['default']);
        }
        return suggestions.slice(0, 5);
    };

    const suggestions = getSuggestions();

    const updateFaq = (index: number, field: 'question' | 'answer', value: string) => {
        const newFaqs = [...faqs];
        if (!newFaqs[index]) {
            newFaqs[index] = { question: '', answer: '' };
        }
        newFaqs[index][field] = value;
        onFaqsChange(newFaqs);
    };

    const useSuggestion = (index: number, question: string) => {
        updateFaq(index, 'question', question);
    };

    // Ensure we always have 5 FAQ slots
    const faqSlots = Array.from({ length: 5 }, (_, i) => faqs[i] || { question: '', answer: '' });

    return (
        <WizardStep
            title="Seed Common Questions"
            description="Pre-populate answers to questions you're frequently asked"
        >
            <div className="max-w-2xl mx-auto space-y-6">
                {/* Info Banner */}
                <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl flex items-start gap-3">
                    <svg className="w-5 h-5 text-indigo-400 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <div>
                        <p className="text-sm text-indigo-200 font-medium">Pro Tip</p>
                        <p className="text-xs text-indigo-300/70 mt-1">
                            These answers become verified knowledge - your twin will answer consistently every time.
                        </p>
                    </div>
                </div>

                {/* FAQ Inputs */}
                <div className="space-y-4">
                    {faqSlots.map((faq, index) => (
                        <div key={index} className="p-4 bg-white/5 border border-white/10 rounded-2xl space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                                    Q&A #{index + 1}
                                </span>
                                {suggestions[index] && !faq.question && (
                                    <button
                                        onClick={() => useSuggestion(index, suggestions[index])}
                                        className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                                    >
                                        Use suggestion
                                    </button>
                                )}
                            </div>

                            <div className="space-y-2">
                                <input
                                    type="text"
                                    value={faq.question}
                                    onChange={(e) => updateFaq(index, 'question', e.target.value)}
                                    placeholder={suggestions[index] || 'Enter a common question...'}
                                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-sm transition-all"
                                />
                                <textarea
                                    value={faq.answer}
                                    onChange={(e) => updateFaq(index, 'answer', e.target.value)}
                                    placeholder="Your verified answer..."
                                    rows={2}
                                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-sm transition-all resize-none"
                                />
                            </div>
                        </div>
                    ))}
                </div>

                {/* Skip Note */}
                <p className="text-center text-xs text-slate-500">
                    You can skip this step and add FAQs later from your dashboard
                </p>
            </div>
        </WizardStep>
    );
}
