'use client';

import React, { useState, useRef, useEffect } from 'react';
import { WizardStep } from '../Wizard';

interface Message {
    role: 'user' | 'assistant' | 'system';
    content: string;
    questionId?: string;
}

interface CollectedData {
    [key: string]: string;
}

interface FirstChatStepProps {
    twinName: string;
    twinId?: string;
    onDataCollected?: (data: CollectedData) => void;
}

// Onboarding questions based on delphi.ai pattern
const INTERVIEW_QUESTIONS = [
    {
        id: 'background',
        targetNode: 'profile.background',
        question: "Let's start with getting to know you! Tell me about your professional background. What do you do and how did you get here?",
        followUp: "Could you share a bit more about your career journey? What are some key roles or experiences that shaped who you are today?"
    },
    {
        id: 'expertise',
        targetNode: 'profile.expertise_areas',
        question: "What topics are you most knowledgeable about? What could you talk about for hours without getting tired?",
        followUp: "If someone introduced you as an expert in something, what would that be?"
    },
    {
        id: 'common_questions',
        targetNode: 'knowledge.common_questions',
        question: "What questions do people ask you most often? What do people always want to know from you?",
        followUp: "If you had a FAQ page, what would be the top 3 questions on it?"
    },
    {
        id: 'key_insights',
        targetNode: 'knowledge.key_insights',
        question: "What are the most important lessons you've learned that you want to share with others?",
        followUp: "If you could only teach someone THREE things, what would they be?"
    },
    {
        id: 'unique_perspective',
        targetNode: 'profile.unique_perspective',
        question: "What makes YOUR perspective on these topics unique? What do you see that others might miss?",
        followUp: "What's something you believe that most people in your field would disagree with?"
    },
    {
        id: 'communication_style',
        targetNode: 'style.communication',
        question: "Last question! How would you describe your communication style? Are you more direct and concise, or do you prefer detailed explanations with lots of examples?",
        followUp: "When explaining something, do you use lots of stories, or do you prefer to get straight to the point?"
    }
];

export function FirstChatStep({ twinName, twinId, onDataCollected }: FirstChatStepProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
    const [collectedData, setCollectedData] = useState<CollectedData>({});
    const [isTyping, setIsTyping] = useState(false);
    const [isComplete, setIsComplete] = useState(false);
    const [needsFollowUp, setNeedsFollowUp] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const progress = Math.round((currentQuestionIndex / INTERVIEW_QUESTIONS.length) * 100);

    // Scroll to bottom helper - defined before useEffect that depends on it
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    // Complete interview function - defined before it's used
    const completeInterview = () => {
        setIsTyping(true);

        setTimeout(() => {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `🎉 **That's all the questions I have!**

I've learned a lot about you:
- **Background**: ${collectedData.background?.substring(0, 50)}...
- **Expertise**: ${collectedData.expertise?.substring(0, 50)}...
- **Common Questions**: People ask about ${collectedData.common_questions?.substring(0, 40)}...
- **Key Insights**: ${collectedData.key_insights?.substring(0, 50)}...

Your digital twin, **${twinName}**, is now ready to represent you! 🚀

Click "Get Started" to go to your dashboard.`
            }]);
            setIsTyping(false);
            setIsComplete(true);
            onDataCollected?.(collectedData);
        }, 1000);
    };

    // Ask question function - defined before useEffect that calls it
    const askQuestion = (index: number) => {
        if (index >= INTERVIEW_QUESTIONS.length) {
            // All questions answered - complete the interview
            completeInterview();
            return;
        }

        setIsTyping(true);

        setTimeout(() => {
            const question = INTERVIEW_QUESTIONS[index];
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: question.question,
                questionId: question.id
            }]);
            setIsTyping(false);
        }, 800);
    };

    // Initialize with first question - uses askQuestion which is now defined above
    useEffect(() => {
        const welcomeMessage: Message = {
            role: 'assistant',
            content: `Hi! 👋 I'm here to learn about you so I can become your digital twin. I'll ask you a few questions to understand your background, expertise, and style. This usually takes about 5 minutes.

Let's get started!`,
        };

        setMessages([welcomeMessage]);

        // Ask first question after delay
        const timer = setTimeout(() => {
            askQuestion(0);
        }, 1500);

        return () => clearTimeout(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Scroll when messages change
    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const askFollowUp = (index: number) => {
        setIsTyping(true);

        setTimeout(() => {
            const question = INTERVIEW_QUESTIONS[index];
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: question.followUp,
                questionId: question.id + '_followup'
            }]);
            setIsTyping(false);
            setNeedsFollowUp(false);
        }, 800);
    };

    const handleSend = async () => {
        if (!input.trim() || isTyping) return;

        const userMessage: Message = { role: 'user', content: input };
        setMessages(prev => [...prev, userMessage]);

        const currentQuestion = INTERVIEW_QUESTIONS[currentQuestionIndex];
        const response = input.trim();

        // Store the response
        const newCollectedData = {
            ...collectedData,
            [currentQuestion.id]: collectedData[currentQuestion.id]
                ? collectedData[currentQuestion.id] + ' ' + response
                : response
        };
        setCollectedData(newCollectedData);

        setInput('');

        // Check if response is too short (needs follow-up)
        if (response.split(' ').length < 10 && !needsFollowUp) {
            setNeedsFollowUp(true);
            // Acknowledge briefly then ask follow-up
            setIsTyping(true);
            setTimeout(() => {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: "Got it! Let me dig a little deeper..."
                }]);
                setIsTyping(false);
                setTimeout(() => askFollowUp(currentQuestionIndex), 500);
            }, 600);
        } else {
            // Move to next question
            const nextIndex = currentQuestionIndex + 1;
            setCurrentQuestionIndex(nextIndex);
            setNeedsFollowUp(false);

            // Acknowledge and move on
            setIsTyping(true);
            setTimeout(() => {
                const acknowledgments = [
                    "Great, thanks for sharing that! 📝",
                    "Perfect, that's really helpful! ✨",
                    "Awesome, I'm learning a lot about you! 🎯",
                    "Thanks! That gives me great insight. 💡",
                    "Wonderful, that's exactly what I needed! 👍",
                    "Excellent! Your perspective is unique. 🌟"
                ];
                const ack = acknowledgments[currentQuestionIndex % acknowledgments.length];

                setMessages(prev => [...prev, { role: 'assistant', content: ack }]);
                setIsTyping(false);

                setTimeout(() => askQuestion(nextIndex), 800);
            }, 600);
        }
    };

    return (
        <WizardStep
            title="Training Interview"
            description={`I'll ask you ${INTERVIEW_QUESTIONS.length} questions to learn about you`}
        >
            <div className="max-w-2xl mx-auto">
                {/* Progress Bar */}
                <div className="mb-4">
                    <div className="flex justify-between text-xs text-slate-500 mb-1">
                        <span>Question {Math.min(currentQuestionIndex + 1, INTERVIEW_QUESTIONS.length)} of {INTERVIEW_QUESTIONS.length}</span>
                        <span>{progress}% complete</span>
                    </div>
                    <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>

                {/* Chat Container */}
                <div className="bg-slate-900/50 border border-white/10 rounded-2xl overflow-hidden">
                    {/* Messages */}
                    <div className="h-[400px] overflow-y-auto p-4 space-y-4 scrollbar-thin">
                        {messages.map((message, index) => (
                            <div
                                key={index}
                                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div className={`flex items-start gap-3 max-w-[85%] ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                    {/* Avatar */}
                                    <div className={`
                    w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
                    ${message.role === 'user'
                                            ? 'bg-indigo-500'
                                            : 'bg-gradient-to-br from-emerald-500 to-teal-600'}
                  `}>
                                        {message.role === 'user' ? (
                                            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                            </svg>
                                        ) : (
                                            <span className="text-white text-xs">🧠</span>
                                        )}
                                    </div>

                                    {/* Message Bubble */}
                                    <div className={`
                    px-4 py-3 rounded-2xl whitespace-pre-wrap
                    ${message.role === 'user'
                                            ? 'bg-indigo-500 text-white rounded-br-sm'
                                            : 'bg-white/10 text-white rounded-bl-sm'}
                  `}>
                                        {message.content}
                                    </div>
                                </div>
                            </div>
                        ))}

                        {/* Typing Indicator */}
                        {isTyping && (
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                                    <span className="text-xs">🧠</span>
                                </div>
                                <div className="px-4 py-3 bg-white/10 rounded-2xl rounded-bl-sm">
                                    <div className="flex gap-1">
                                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div className="p-4 border-t border-white/10">
                        {isComplete ? (
                            <div className="text-center py-4">
                                <div className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500/20 text-emerald-400 rounded-xl text-sm font-medium">
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                    </svg>
                                    Interview Complete! Click "Get Started" below.
                                </div>
                            </div>
                        ) : (
                            <form
                                onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                                className="flex gap-3"
                            >
                                <input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    placeholder="Type your answer..."
                                    disabled={isTyping}
                                    className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all disabled:opacity-50"
                                />
                                <button
                                    type="submit"
                                    disabled={!input.trim() || isTyping}
                                    className="px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-semibold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                    </svg>
                                </button>
                            </form>
                        )}
                    </div>
                </div>

                {/* Cluster indicator */}
                <div className="flex justify-center gap-2 mt-4">
                    {['profile', 'knowledge', 'style'].map((cluster, idx) => {
                        const clusterQuestions = INTERVIEW_QUESTIONS.filter(q =>
                            q.targetNode.startsWith(cluster.replace('knowledge', 'knowledge').replace('profile', 'profile'))
                        );
                        const clusterStart = INTERVIEW_QUESTIONS.findIndex(q =>
                            q.targetNode.startsWith(cluster === 'profile' ? 'profile' : cluster === 'knowledge' ? 'knowledge' : 'style')
                        );
                        const isActive = currentQuestionIndex >= clusterStart &&
                            currentQuestionIndex < clusterStart + (cluster === 'profile' ? 4 : cluster === 'knowledge' ? 2 : 1);
                        const isComplete = currentQuestionIndex > clusterStart + (cluster === 'profile' ? 3 : cluster === 'knowledge' ? 1 : 0);

                        return (
                            <div key={cluster} className={`
                px-3 py-1.5 rounded-lg text-xs font-medium transition-all
                ${isActive ? 'bg-indigo-500/20 text-indigo-400' :
                                    isComplete ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/5 text-slate-500'}
              `}>
                                {cluster === 'profile' ? '👤 Your Profile' :
                                    cluster === 'knowledge' ? '📚 Your Knowledge' : '💬 Your Style'}
                            </div>
                        );
                    })}
                </div>

                {/* Tips */}
                <p className="text-center text-slate-500 text-xs mt-4">
                    💡 Tip: Be detailed! The more you share, the better your twin will represent you.
                </p>
            </div>
        </WizardStep>
    );
}

export default FirstChatStep;
