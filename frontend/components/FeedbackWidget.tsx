// frontend/components/FeedbackWidget.tsx
/**
 * User Feedback Widget for chat responses
 * 
 * Displays thumbs up/down buttons with optional reason dropdown.
 * Submits feedback to Langfuse via backend API.
 */

import React, { useState } from 'react';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

interface FeedbackWidgetProps {
    traceId: string;
    messageId?: string;
    onFeedbackSubmitted?: (success: boolean) => void;
}

type FeedbackReason =
    | 'great_answer'
    | 'helpful'
    | 'incorrect'
    | 'hallucination'
    | 'off_topic'
    | 'incomplete'
    | 'other';

const POSITIVE_REASONS: { value: FeedbackReason; label: string }[] = [
    { value: 'great_answer', label: 'Great answer' },
    { value: 'helpful', label: 'Helpful' },
];

const NEGATIVE_REASONS: { value: FeedbackReason; label: string }[] = [
    { value: 'incorrect', label: 'Incorrect information' },
    { value: 'hallucination', label: 'Made up facts' },
    { value: 'off_topic', label: 'Off topic' },
    { value: 'incomplete', label: 'Incomplete answer' },
    { value: 'other', label: 'Other' },
];

const FeedbackWidget: React.FC<FeedbackWidgetProps> = ({
    traceId,
    messageId,
    onFeedbackSubmitted,
}) => {
    const [selectedScore, setSelectedScore] = useState<1 | -1 | null>(null);
    const [selectedReason, setSelectedReason] = useState<FeedbackReason | null>(null);
    const [comment, setComment] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitted, setSubmitted] = useState(false);

    const handleScoreClick = (score: 1 | -1) => {
        if (submitted) return;
        setSelectedScore(score);
        setSelectedReason(null); // Reset reason when changing score
    };

    const handleSubmit = async () => {
        if (!selectedScore || !selectedReason) return;

        setIsSubmitting(true);
        try {
            const response = await authFetchStandalone(`/feedback/${encodeURIComponent(traceId)}`, {
                method: 'POST',
                body: JSON.stringify({
                    score: selectedScore,
                    reason: selectedReason,
                    comment: comment || undefined,
                    message_id: messageId,
                }),
            });

            if (response.ok) {
                setSubmitted(true);
                onFeedbackSubmitted?.(true);
            } else {
                console.error('Failed to submit feedback');
                onFeedbackSubmitted?.(false);
            }
        } catch (error) {
            console.error('Error submitting feedback:', error);
            onFeedbackSubmitted?.(false);
        } finally {
            setIsSubmitting(false);
        }
    };

    const reasons = selectedScore === 1 ? POSITIVE_REASONS : NEGATIVE_REASONS;

    if (submitted) {
        return (
            <div className="feedback-widget feedback-submitted">
                <span className="feedback-thanks">✓ Thanks for your feedback!</span>
            </div>
        );
    }

    return (
        <div className="feedback-widget">
            <div className="feedback-buttons">
                <button
                    className={`feedback-btn thumbs-up ${selectedScore === 1 ? 'selected' : ''}`}
                    onClick={() => handleScoreClick(1)}
                    title="Good response"
                    disabled={isSubmitting}
                >
                    👍
                </button>
                <button
                    className={`feedback-btn thumbs-down ${selectedScore === -1 ? 'selected' : ''}`}
                    onClick={() => handleScoreClick(-1)}
                    title="Bad response"
                    disabled={isSubmitting}
                >
                    👎
                </button>
            </div>

            {selectedScore !== null && (
                <div className="feedback-reason-panel">
                    <select
                        value={selectedReason || ''}
                        onChange={(e) => setSelectedReason(e.target.value as FeedbackReason)}
                        className="feedback-reason-select"
                        disabled={isSubmitting}
                    >
                        <option value="">Select a reason...</option>
                        {reasons.map((r) => (
                            <option key={r.value} value={r.value}>
                                {r.label}
                            </option>
                        ))}
                    </select>

                    {selectedReason === 'other' && (
                        <input
                            type="text"
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            placeholder="Tell us more..."
                            className="feedback-comment"
                            maxLength={500}
                            disabled={isSubmitting}
                        />
                    )}

                    <button
                        className="feedback-submit"
                        onClick={handleSubmit}
                        disabled={!selectedReason || isSubmitting}
                    >
                        {isSubmitting ? 'Submitting...' : 'Submit'}
                    </button>
                </div>
            )}

            <style jsx>{`
        .feedback-widget {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding: 8px;
          font-size: 14px;
        }

        .feedback-buttons {
          display: flex;
          gap: 8px;
        }

        .feedback-btn {
          background: transparent;
          border: 1px solid #ddd;
          border-radius: 4px;
          padding: 4px 8px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .feedback-btn:hover {
          background: #f5f5f5;
        }

        .feedback-btn.selected {
          border-color: #4a90d9;
          background: #e8f0fe;
        }

        .feedback-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .feedback-reason-panel {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding: 8px;
          background: #f9f9f9;
          border-radius: 4px;
        }

        .feedback-reason-select {
          padding: 6px;
          border: 1px solid #ddd;
          border-radius: 4px;
        }

        .feedback-comment {
          padding: 6px;
          border: 1px solid #ddd;
          border-radius: 4px;
        }

        .feedback-submit {
          background: #4a90d9;
          color: white;
          border: none;
          border-radius: 4px;
          padding: 8px 16px;
          cursor: pointer;
          font-weight: 500;
        }

        .feedback-submit:disabled {
          background: #ccc;
          cursor: not-allowed;
        }

        .feedback-submitted {
          color: #28a745;
        }

        .feedback-thanks {
          font-size: 13px;
        }
      `}</style>
        </div>
    );
};

export default FeedbackWidget;
