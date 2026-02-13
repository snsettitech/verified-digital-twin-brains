'use client';

import React, { useEffect, useRef, useCallback } from 'react';

export interface Citation {
  id: string;
  filename?: string | null;
  citation_url?: string | null;
  confidence_score?: number;
  chunk_preview?: string;
}

interface CitationsDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  citations: Citation[];
}

export function CitationsDrawer({ isOpen, onClose, citations }: CitationsDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Handle escape key
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  // Lock body scroll when open
  useEffect(() => {
    if (isOpen) {
      // Store previously focused element
      previouslyFocusedRef.current = document.activeElement as HTMLElement;
      
      // Lock scroll
      const originalStyle = window.getComputedStyle(document.body).overflow;
      document.body.style.overflow = 'hidden';
      
      // Add escape key listener
      document.addEventListener('keydown', handleKeyDown);
      
      // Focus close button after animation
      const timer = setTimeout(() => {
        closeButtonRef.current?.focus();
      }, 100);
      
      return () => {
        document.body.style.overflow = originalStyle;
        document.removeEventListener('keydown', handleKeyDown);
        clearTimeout(timer);
      };
    } else {
      // Restore focus when closing
      if (previouslyFocusedRef.current) {
        previouslyFocusedRef.current.focus();
      }
    }
  }, [isOpen, handleKeyDown]);

  // Handle backdrop click
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    // Only close if clicking the backdrop itself, not the drawer
    if (e.target === e.currentTarget) {
      onClose();
    }
  }, [onClose]);

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="citations-title"
    >
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
        aria-hidden="true"
      />
      
      {/* Drawer */}
      <div 
        ref={drawerRef}
        className="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl transform transition-transform duration-300 ease-out animate-in slide-in-from-right"
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-100">
            <div>
              <h2 id="citations-title" className="text-lg font-bold text-slate-900">Sources</h2>
              <p className="text-sm text-slate-500 mt-1">
                {citations.length} source{citations.length !== 1 ? 's' : ''} referenced
              </p>
            </div>
            <button
              ref={closeButtonRef}
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-slate-100 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Close drawer"
            >
              <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {citations.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <p className="text-slate-500">No sources available for this response</p>
                <p className="text-sm text-slate-400 mt-2">
                  Try asking a question about your uploaded documents
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {citations.map((citation, index) => (
                  <div 
                    key={citation.id}
                    className="p-4 bg-slate-50 rounded-xl border border-slate-100 hover:border-indigo-200 transition-colors focus-within:ring-2 focus-within:ring-indigo-500"
                    tabIndex={0}
                  >
                    <div className="flex items-start gap-3">
                      <span className="flex-shrink-0 w-8 h-8 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center text-sm font-bold">
                        {index + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="font-medium text-slate-900 break-words">
                            {citation.filename || 'Unknown Source'}
                          </p>
                          {/* Confidence Score Badge */}
                          {citation.confidence_score !== undefined && (
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                              citation.confidence_score >= 0.7 
                                ? 'bg-green-100 text-green-700' 
                                : citation.confidence_score >= 0.4
                                ? 'bg-yellow-100 text-yellow-700'
                                : 'bg-red-100 text-red-700'
                            }`}>
                              {(citation.confidence_score * 100).toFixed(0)}% match
                            </span>
                          )}
                        </div>
                        
                        {/* Chunk Preview */}
                        {citation.chunk_preview && (
                          <p className="mt-2 text-sm text-slate-600 line-clamp-3 italic">
                            &ldquo;{citation.chunk_preview}&rdquo;
                          </p>
                        )}
                        
                        {citation.citation_url && (
                          <a
                            href={citation.citation_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-2 inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                            </svg>
                            View source
                          </a>
                        )}
                        <p className="mt-2 text-xs text-slate-400 font-mono">
                          Source ID: {citation.id.slice(0, 8)}...
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-6 border-t border-slate-100 bg-slate-50/50">
            <button
              onClick={onClose}
              className="w-full py-3 bg-slate-900 text-white font-semibold rounded-xl hover:bg-slate-800 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Inline citation component
interface InlineCitationProps {
  number: number;
  onClick: () => void;
}

export function InlineCitation({ number, onClick }: InlineCitationProps) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center justify-center w-5 h-5 ml-0.5 text-[10px] font-bold bg-indigo-100 text-indigo-600 rounded-full hover:bg-indigo-200 hover:text-indigo-700 transition-colors align-super focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
      title={`View source ${number}`}
      aria-label={`Citation ${number}`}
      type="button"
    >
      {number}
    </button>
  );
}

// Parse content and insert inline citations
export function parseCitations(
  content: string, 
  citations: Citation[], 
  onCitationClick: (index: number) => void
): React.ReactNode[] {
  if (!citations || citations.length === 0) {
    return [<span key="content">{content}</span>];
  }

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  // Simple regex to find citation markers like [source:uuid] or [1], [2]
  // This is a basic implementation - can be enhanced based on actual citation format
  const citationRegex = /\[(?:source:)?([a-f0-9-]{36}|\d+)\]/gi;
  let match;
  let citationIndex = 0;

  while ((match = citationRegex.exec(content)) !== null && citationIndex < citations.length) {
    // Add text before citation
    if (match.index > lastIndex) {
      parts.push(
        <span key={`text-${lastIndex}`}>
          {content.slice(lastIndex, match.index)}
        </span>
      );
    }

    // Add citation marker
    const currentIndex = citationIndex;
    parts.push(
      <InlineCitation
        key={`cite-${match.index}`}
        number={currentIndex + 1}
        onClick={() => onCitationClick(currentIndex)}
      />
    );

    lastIndex = match.index + match[0].length;
    citationIndex++;
  }

  // Add remaining text
  if (lastIndex < content.length) {
    parts.push(<span key={`text-${lastIndex}`}>{content.slice(lastIndex)}</span>);
  }

  // If no citations found in text, append them at the end
  if (parts.length === 1 && citations.length > 0) {
    parts.push(
      <span key="citations" className="inline-flex gap-1 ml-1">
        {citations.map((_, idx) => (
          <InlineCitation
            key={`end-cite-${idx}`}
            number={idx + 1}
            onClick={() => onCitationClick(idx)}
          />
        ))}
      </span>
    );
  }

  return parts;
}
