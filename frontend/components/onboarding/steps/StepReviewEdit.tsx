'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/Card';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

interface StepReviewEditProps {
  twinId: string;
  onComplete: () => void;
}

interface EditableFields {
  display_name: string;
  headline: string;
  bio: string;
  short_description: string;
  areas_of_expertise: string;   // newline-separated in textarea
  pinned_questions: string;     // newline-separated in textarea
  nationality: string;
  birth_year: string;
}

interface WorkEntry {
  company?: string;
  role?: string;
  description?: string;
  start_year?: number;
  end_year?: number;
}

interface EducationEntry {
  institution?: string;
  degree?: string;
  field?: string;
  end_year?: number;
}

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

function LabeledInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm"
      />
    </div>
  );
}

function LabeledTextarea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors text-sm resize-none"
      />
    </div>
  );
}

export function StepReviewEdit({ twinId, onComplete }: StepReviewEditProps) {
  const [fields, setFields] = useState<EditableFields | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [workExperience, setWorkExperience] = useState<WorkEntry[]>([]);
  const [education, setEducation] = useState<EducationEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showAddContent, setShowAddContent] = useState(false);
  const [pasteContent, setPasteContent] = useState('');
  const [isSubmittingPaste, setIsSubmittingPaste] = useState(false);
  const [pasteSubmitted, setPasteSubmitted] = useState(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const res = await authFetchStandalone(`/twins/${twinId}`);
        if (!res.ok) throw new Error(`Failed to load profile (${res.status})`);
        const twin = await res.json();
        const pp = twin?.settings?.public_profile ?? {};
        setFields({
          display_name: pp.display_name ?? twin?.name ?? '',
          headline: pp.headline ?? '',
          bio: pp.bio ?? '',
          short_description: pp.short_description ?? '',
          areas_of_expertise: (pp.areas_of_expertise ?? []).join('\n'),
          pinned_questions: (pp.pinned_questions ?? []).join('\n'),
          nationality: pp.nationality ?? '',
          birth_year: pp.birth_year ? String(pp.birth_year) : '',
        });
        setImageUrl(pp.image_url ?? pp.avatar_url ?? null);
        setWorkExperience(pp.work_experience ?? []);
        setEducation(pp.education ?? []);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : 'Failed to load profile');
      } finally {
        setIsLoading(false);
      }
    }
    void load();
  }, [twinId]);

  const handleSave = useCallback(async () => {
    if (!fields) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      const birthYearNum = fields.birth_year.trim()
        ? parseInt(fields.birth_year.trim(), 10) || undefined
        : undefined;

      const publicProfile: Record<string, unknown> = {
        display_name: fields.display_name.trim() || undefined,
        headline: fields.headline.trim() || undefined,
        bio: fields.bio.trim() || undefined,
        short_description: fields.short_description.trim() || undefined,
        areas_of_expertise: fields.areas_of_expertise
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
        pinned_questions: fields.pinned_questions
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
        nationality: fields.nationality.trim() || undefined,
        birth_year: birthYearNum,
      };

      const res = await authFetchStandalone(`/twins/${twinId}`, {
        method: 'PATCH',
        body: JSON.stringify({ settings: { public_profile: publicProfile } }),
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(
          (payload?.detail as string) ??
          (payload?.detail?.message as string) ??
          `Save failed (${res.status})`
        );
      }

      onComplete();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  }, [fields, twinId, onComplete]);

  const handleSubmitPaste = useCallback(async () => {
    if (!pasteContent.trim()) return;
    setIsSubmittingPaste(true);
    try {
      await authFetchStandalone('/persona/link-compile/jobs/mode-b', {
        method: 'POST',
        body: JSON.stringify({
          twin_id: twinId,
          content: pasteContent,
          title: 'Additional Content',
        }),
      });
      setPasteContent('');
      setPasteSubmitted(true);
      setShowAddContent(false);
    } catch (err) {
      console.error('[StepReviewEdit] Mode B paste failed:', err);
    } finally {
      setIsSubmittingPaste(false);
    }
  }, [pasteContent, twinId]);

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 bg-slate-800 rounded-lg w-2/3 mx-auto" />
        <div className="h-4 bg-slate-800 rounded w-1/2 mx-auto" />
        <div className="h-48 bg-slate-800 rounded-xl" />
        <div className="h-48 bg-slate-800 rounded-xl" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-6 bg-red-500/10 border border-red-500/30 rounded-xl text-center">
        <p className="text-red-400 mb-4">{loadError}</p>
        <button
          onClick={onComplete}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium"
        >
          Continue to dashboard
        </button>
      </div>
    );
  }

  if (!fields) return null;

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 bg-green-500/10 border border-green-500/20 rounded-full mb-4">
          <span className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-xs font-medium text-green-400">Your persona is live</span>
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Review Your Profile</h2>
        <p className="text-slate-400 text-sm max-w-md mx-auto">
          We researched the web and built your profile. Confirm or edit anything before heading to your dashboard.
        </p>
      </div>

      {/* Profile image */}
      <Card className="p-5 bg-slate-900 border-slate-700">
        <div className="flex items-center gap-4">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={fields.display_name}
              className="w-16 h-16 rounded-2xl object-cover border border-slate-700"
            />
          ) : (
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-semibold text-lg">
              {getInitials(fields.display_name) || 'P'}
            </div>
          )}
          <div>
            <p className="text-sm font-medium text-white">{fields.display_name || 'Your Persona'}</p>
            <p className="text-xs text-slate-500 mt-0.5">
              {imageUrl
                ? 'Profile image set from LinkedIn or research. Change it later in Settings.'
                : 'No image found — you can upload one in Settings.'}
            </p>
          </div>
        </div>
      </Card>

      {/* Editable fields */}
      <Card className="p-6 bg-slate-900 border-slate-700 space-y-5">
        <LabeledInput
          label="Display Name"
          value={fields.display_name}
          onChange={(v) => setFields((f) => f && { ...f, display_name: v })}
          placeholder="Your full name"
        />
        <LabeledInput
          label="Headline"
          value={fields.headline}
          onChange={(v) => setFields((f) => f && { ...f, headline: v })}
          placeholder="e.g. Founder at Acme"
        />
        <LabeledTextarea
          label="Bio"
          rows={4}
          value={fields.bio}
          onChange={(v) => setFields((f) => f && { ...f, bio: v })}
          placeholder="A short bio about you…"
        />
        <LabeledTextarea
          label="Short Description"
          rows={2}
          value={fields.short_description}
          onChange={(v) => setFields((f) => f && { ...f, short_description: v })}
          placeholder="One sentence summary"
        />
        <LabeledTextarea
          label="Areas of Expertise (one per line)"
          rows={3}
          value={fields.areas_of_expertise}
          onChange={(v) => setFields((f) => f && { ...f, areas_of_expertise: v })}
          placeholder={"Public Administration\nPolitical Strategy"}
        />
        <LabeledTextarea
          label="Pinned Questions (one per line)"
          rows={3}
          value={fields.pinned_questions}
          onChange={(v) => setFields((f) => f && { ...f, pinned_questions: v })}
          placeholder={"What are your key initiatives?\nHow do you approach leadership?"}
        />
        <div className="grid grid-cols-2 gap-4">
          <LabeledInput
            label="Nationality (optional)"
            value={fields.nationality}
            onChange={(v) => setFields((f) => f && { ...f, nationality: v })}
            placeholder="e.g. Indian"
          />
          <LabeledInput
            label="Birth Year (optional)"
            value={fields.birth_year}
            onChange={(v) => setFields((f) => f && { ...f, birth_year: v })}
            placeholder="e.g. 1975"
          />
        </div>
      </Card>

      {/* Work / education — display-only */}
      {(workExperience.length > 0 || education.length > 0) && (
        <Card className="p-5 bg-slate-900 border-slate-700">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">
            Extracted from research
          </p>
          {workExperience.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-slate-400 mb-2 font-medium">Work Experience</p>
              <ul className="space-y-1">
                {workExperience.slice(0, 4).map((w, i) => (
                  <li key={i} className="text-sm text-slate-300">
                    {[w.role, w.company].filter(Boolean).join(' at ')}
                    {(w.start_year || w.end_year) && (
                      <span className="text-slate-500 ml-2 text-xs">
                        {w.start_year ?? '?'}–{w.end_year ?? 'present'}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {education.length > 0 && (
            <div>
              <p className="text-xs text-slate-400 mb-2 font-medium">Education</p>
              <ul className="space-y-1">
                {education.slice(0, 3).map((e, i) => (
                  <li key={i} className="text-sm text-slate-300">
                    {[e.degree, e.field].filter(Boolean).join(' in ')}
                    {e.institution && <span className="text-slate-400"> — {e.institution}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="text-xs text-slate-600 mt-3">Edit work history and education in your dashboard.</p>
        </Card>
      )}

      {/* Save error */}
      {saveError && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-red-400 text-sm">{saveError}</p>
        </div>
      )}

      {/* Primary CTA */}
      <button
        onClick={handleSave}
        disabled={isSaving}
        className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl font-semibold text-lg transition-colors"
      >
        {isSaving ? 'Saving…' : 'Looks good — go to dashboard'}
      </button>

      {/* Add more content accordion */}
      <div className="border border-slate-700 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowAddContent(!showAddContent)}
          className="w-full px-6 py-4 flex items-center justify-between text-slate-400 hover:text-white bg-slate-900/50 transition-colors"
        >
          <span className="text-sm font-medium">
            Add more content to improve your persona
          </span>
          <span className="text-lg">{showAddContent ? '−' : '+'}</span>
        </button>
        {showAddContent && (
          <div className="p-6 bg-slate-900 border-t border-slate-700 space-y-4">
            {pasteSubmitted && (
              <p className="text-sm text-green-400">Content submitted — it will be processed in the background.</p>
            )}
            <p className="text-sm text-slate-400">
              Paste a bio, article, interview transcript, or any other text about you.
              It will be indexed and used to improve chat responses.
            </p>
            <textarea
              value={pasteContent}
              onChange={(e) => setPasteContent(e.target.value)}
              placeholder="Paste text here…"
              rows={5}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors resize-none"
            />
            <button
              type="button"
              onClick={handleSubmitPaste}
              disabled={isSubmittingPaste || !pasteContent.trim()}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
            >
              {isSubmittingPaste ? 'Submitting…' : 'Submit content'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
