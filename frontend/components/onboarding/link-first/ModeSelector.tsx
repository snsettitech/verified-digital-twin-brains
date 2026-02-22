'use client';

import { Card } from '@/components/ui/Card';

interface ModeSelectorProps {
  onSelect: (mode: 'manual' | 'link_first') => void;
}

// Feature flag: Link-First mode enabled
const LINK_FIRST_ENABLED = process.env.NEXT_PUBLIC_LINK_FIRST_ENABLED === 'true';

export function ModeSelector({ onSelect }: ModeSelectorProps) {
  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold mb-2 text-white">Choose Your Path</h2>
        <p className="text-slate-400">
          How would you like to build your Digital Twin?
        </p>
      </div>

      <div className={`grid gap-6 ${LINK_FIRST_ENABLED ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 max-w-md mx-auto'}`}>
        {/* Manual Mode - Always Available */}
        <Card 
          className="p-6 cursor-pointer hover:border-indigo-500 transition-colors border-2 border-slate-700 bg-slate-900"
          onClick={() => onSelect('manual')}
        >
          <div className="text-center">
            <span className="text-4xl mb-4 block">✍️</span>
            <h3 className="text-xl font-semibold mb-2 text-white">Manual Setup</h3>
            <p className="text-slate-400 text-sm">
              Answer questions about your identity, thinking style, values, and communication preferences.
            </p>
            <ul className="text-left text-sm text-slate-300 mt-4 space-y-1">
              <li>✓ 6-step guided questionnaire</li>
              <li>✓ Immediate chat access</li>
              <li>✓ Best for clear self-knowledge</li>
            </ul>
          </div>
        </Card>

        {/* Link-First Mode - Feature Flag Gated */}
        {LINK_FIRST_ENABLED && (
          <Card 
            className="p-6 cursor-pointer hover:border-indigo-500 transition-colors border-2 border-slate-700 bg-slate-900"
            onClick={() => onSelect('link_first')}
          >
            <div className="text-center">
              <span className="text-4xl mb-4 block">🔗</span>
              <h3 className="text-xl font-semibold mb-2 text-white">Link-First</h3>
              <p className="text-slate-400 text-sm">
                Import content from your writing, exports, and public profiles.
              </p>
              <ul className="text-left text-sm text-slate-300 mt-4 space-y-1">
                <li>✓ Import LinkedIn, Twitter, articles</li>
                <li>✓ AI extracts claims from content</li>
                <li>✓ Verified, citable persona</li>
              </ul>
              <span className="inline-block mt-4 px-3 py-1 bg-indigo-500/20 text-indigo-400 text-xs rounded-full">
                Recommended
              </span>
            </div>
          </Card>
        )}
      </div>

      {!LINK_FIRST_ENABLED && (
        <p className="text-center text-sm text-slate-500">
          Link-First mode coming soon. Currently in beta testing.
        </p>
      )}
    </div>
  );
}
