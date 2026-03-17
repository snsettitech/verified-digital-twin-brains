'use client';

/**
 * LinkedInImportCard
 *
 * One-time nudge card shown on the Profile dashboard page when the user has
 * not yet imported their LinkedIn export.  After a successful import (or when
 * the user manually dismisses it) the card disappears and doesn't come back.
 *
 * Usage:
 *   <LinkedInImportCard twinId={twinId} onImported={refreshTwins} />
 */

import React, { useCallback, useRef, useState } from 'react';
import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';

// ─── Types ────────────────────────────────────────────────────────────────────

type ImportResult = {
  fields_imported: string[];
  work_experience_count: number;
  education_count: number;
  skills_count: number;
};

type Props = {
  twinId: string;
  onImported?: () => void;
};

// ─── Icons ────────────────────────────────────────────────────────────────────

function IconLinkedIn() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5 text-[#0077B5]">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function IconUpload() {
  return (
    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function IconX() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function LinkedInImportCard({ twinId, onImported }: Props) {
  const [dismissed, setDismissed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith('.zip')) {
        setError('Please upload the LinkedIn export ZIP file.');
        return;
      }

      setError(null);
      setIsUploading(true);

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await authFetchStandalone(
          `/persona/${encodeURIComponent(twinId)}/import/linkedin-export`,
          { method: 'POST', body: formData },
        );

        if (!response.ok) {
          const text = await response.text();
          let detail = text;
          try {
            const json = JSON.parse(text);
            detail = json.detail || text;
          } catch {}
          throw new Error(detail || 'Upload failed');
        }

        const data: ImportResult = await response.json();
        setResult(data);
        onImported?.();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
      } finally {
        setIsUploading(false);
      }
    },
    [twinId, onImported],
  );

  const onFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) void handleFile(file);
      e.target.value = '';
    },
    [handleFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile],
  );

  if (dismissed) return null;

  // ── Success state ──────────────────────────────────────────────────────────
  if (result) {
    return (
      <div className="relative flex items-start gap-4 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
          <IconCheck />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-emerald-800">LinkedIn data imported</p>
          <p className="mt-0.5 text-xs text-emerald-700">
            Imported {result.fields_imported.length} fields
            {result.work_experience_count > 0 && ` · ${result.work_experience_count} jobs`}
            {result.education_count > 0 && ` · ${result.education_count} degrees`}
            {result.skills_count > 0 && ` · ${result.skills_count} skills`}
          </p>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="shrink-0 rounded-lg p-1.5 text-emerald-500 transition-colors hover:bg-emerald-100 hover:text-emerald-700"
          aria-label="Dismiss"
        >
          <IconX />
        </button>
      </div>
    );
  }

  // ── Default state ──────────────────────────────────────────────────────────
  return (
    <div className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {/* Dismiss button */}
      <button
        onClick={() => setDismissed(true)}
        className="absolute right-3 top-3 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        aria-label="Dismiss"
      >
        <IconX />
      </button>

      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#0077B5]/10">
          <IconLinkedIn />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900">Import LinkedIn data</p>
          <p className="text-xs text-slate-500">Fill work history, education &amp; skills automatically</p>
        </div>
      </div>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
        className={[
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 text-center transition-colors',
          isDragging
            ? 'border-[#0077B5] bg-[#0077B5]/5'
            : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50',
          isUploading ? 'pointer-events-none opacity-60' : '',
        ].join(' ')}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          className="sr-only"
          onChange={onFileInputChange}
        />
        {isUploading ? (
          <>
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#0077B5] border-t-transparent" />
            <p className="text-xs text-slate-500">Uploading…</p>
          </>
        ) : (
          <>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-500">
              <IconUpload />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-700">
                Drop your LinkedIn export ZIP here
              </p>
              <p className="mt-0.5 text-[11px] text-slate-400">
                or click to browse
              </p>
            </div>
          </>
        )}
      </div>

      {error && (
        <p className="mt-2 text-xs text-rose-600">{error}</p>
      )}

      <p className="mt-3 text-[11px] text-slate-400 leading-4">
        Go to{' '}
        <span className="font-medium text-slate-500">
          LinkedIn → Settings → Data Privacy → Get a copy of your data
        </span>{' '}
        and download the&nbsp;ZIP.
      </p>
    </div>
  );
}

export default LinkedInImportCard;
