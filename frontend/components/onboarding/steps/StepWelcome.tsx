'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';

interface StepWelcomeProps {
  onSubmit: (data: { fullName: string; location?: string; role?: string; consent: boolean }) => void;
}

export function StepWelcome({ onSubmit }: StepWelcomeProps) {
  const [fullName, setFullName] = useState('');
  const [location, setLocation] = useState('');
  const [role, setRole] = useState('');
  const [consent, setConsent] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!fullName.trim() || !consent) return;
    
    setIsSubmitting(true);
    await onSubmit({ 
      fullName: fullName.trim(), 
      location: location.trim() || undefined,
      role: role.trim() || undefined,
      consent 
    });
    setIsSubmitting(false);
  };

  const isValid = fullName.trim().length >= 2 && consent;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-white mb-3">
          Create Your Digital Twin
        </h2>
        <p className="text-slate-400 max-w-md mx-auto">
          We'll search for your public content and build a verified, citable persona.
          Setup takes about 2 minutes.
        </p>
      </div>

      {/* Form */}
      <Card className="p-8 bg-slate-900 border-slate-700">
        <div className="space-y-6">
          {/* Full Name - Required */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Full Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g., Sarah Chen"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
            <p className="text-xs text-slate-500 mt-1">
              We'll search for public links matching this name
            </p>
          </div>

          {/* Location - Optional disambiguation */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Location <span className="text-slate-500">(optional)</span>
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., San Francisco, CA"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
            <p className="text-xs text-slate-500 mt-1">
              Helps disambiguate from others with the same name
            </p>
          </div>

          {/* Role - Optional disambiguation */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Current Role <span className="text-slate-500">(optional)</span>
            </label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g., Partner at Acme Ventures"
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          {/* Consent Checkbox */}
          <div className="pt-4 border-t border-slate-800">
            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="mt-1 w-5 h-5 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500/20"
              />
              <div className="text-sm text-slate-300 group-hover:text-slate-200 transition-colors">
                <span className="font-medium text-white">Search the public web</span> for links that look like me. 
                I understand that only links I select will be stored, and I can add or remove sources at any time.
              </div>
            </label>
          </div>

          {/* Data Policy */}
          <div className="bg-slate-800/50 p-4 rounded-lg border border-slate-700">
            <p className="text-xs text-slate-400">
              <span className="font-medium text-slate-300">Privacy note:</span> We search public web sources only. 
              Unselected search results are not stored. You control what gets added to your twin.
            </p>
          </div>
        </div>
      </Card>

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={!isValid || isSubmitting}
        className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-colors flex items-center justify-center gap-2"
      >
        {isSubmitting ? (
          <>
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Creating...
          </>
        ) : (
          <>
            <span>🔍</span>
            Find My Links
          </>
        )}
      </button>

      {/* Manual Option */}
      <div className="text-center">
        <button
          onClick={() => onSubmit({ fullName: fullName.trim() || 'Anonymous', consent: true, manualMode: true } as any)}
          className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
        >
          Prefer to answer questions manually? →
        </button>
      </div>
    </div>
  );
}
