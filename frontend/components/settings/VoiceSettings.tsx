'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface Voice {
  voice_id: string;
  name: string;
  category?: string;
  description?: string;
}

interface VoiceSettings {
  voice_id: string;
  model_id: string;
  stability: number;
  similarity_boost: number;
  style: number;
  use_speaker_boost: boolean;
}

interface VoiceSettingsProps {
  twinId: string;
}

const DEFAULT_SETTINGS: VoiceSettings = {
  voice_id: '21m00Tcm4TlvDq8ikWAM',
  model_id: 'eleven_monolingual_v1',
  stability: 0.5,
  similarity_boost: 0.75,
  style: 0.0,
  use_speaker_boost: true,
};

export default function VoiceSettings({ twinId }: VoiceSettingsProps) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [settings, setSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const [originalSettings, setOriginalSettings] = useState<VoiceSettings>(DEFAULT_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const supabase = getSupabaseClient();

  const getAuthToken = useCallback(async (): Promise<string | null> => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token || null;
  }, [supabase]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const token = await getAuthToken();
        if (!token) {
          setError('Not authenticated');
          setLoading(false);
          return;
        }

        const voicesRes = await fetch(`${API_BASE_URL}/audio/voices`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (voicesRes.ok) {
          const voicesData = await voicesRes.json();
          setVoices(voicesData.voices || []);
        }

        const settingsRes = await fetch(`${API_BASE_URL}/audio/settings/${twinId}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (settingsRes.ok) {
          const settingsData = await settingsRes.json();
          const loadedSettings = { ...DEFAULT_SETTINGS, ...settingsData.settings };
          setSettings(loadedSettings);
          setOriginalSettings(loadedSettings);
        }
      } catch (err) {
        console.error('Failed to load voice settings:', err);
        setError('Failed to load settings');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [twinId, getAuthToken]);

  useEffect(() => {
    const changed = JSON.stringify(settings) !== JSON.stringify(originalSettings);
    setHasChanges(changed);
  }, [settings, originalSettings]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const token = await getAuthToken();
      if (!token) {
        setError('Not authenticated');
        return;
      }

      const response = await fetch(`${API_BASE_URL}/audio/settings/${twinId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (response.ok) {
        setOriginalSettings(settings);
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        const data = await response.json().catch(() => ({}));
        setError(data.detail || 'Failed to save settings');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);

    try {
      const token = await getAuthToken();
      if (!token) return;

      const testText = "Hello! This is how I will sound when answering questions.";
      
      const response = await fetch(`${API_BASE_URL}/audio/tts/${twinId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: testText }),
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.play();
        audio.onended = () => URL.revokeObjectURL(audioUrl);
      } else {
        setError('Failed to generate test audio');
      }
    } catch (err) {
      setError('Failed to test voice');
    } finally {
      setTesting(false);
    }
  };

  const handleReset = () => {
    setSettings(originalSettings);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-slate-200 rounded animate-pulse" />
        <div className="space-y-4">
          <div className="h-10 bg-slate-200 rounded animate-pulse" />
          <div className="h-10 bg-slate-200 rounded animate-pulse" />
          <div className="h-10 bg-slate-200 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-slate-900">Voice Settings</h3>
        <p className="text-sm text-slate-500 mt-1">
          Configure how your twin sounds when reading responses aloud.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
          <div className="flex items-center gap-2 text-red-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm">{error}</span>
          </div>
        </div>
      )}

      {success && (
        <div className="p-4 bg-green-50 border border-green-100 rounded-xl">
          <div className="flex items-center gap-2 text-green-700">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm font-medium">Settings saved successfully!</span>
          </div>
        </div>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium text-slate-700">Voice</label>
        <select
          value={settings.voice_id}
          onChange={(e) => setSettings(s => ({ ...s, voice_id: e.target.value }))}
          className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        >
          {voices.length === 0 ? (
            <option value={DEFAULT_SETTINGS.voice_id}>Default Voice</option>
          ) : (
            voices.map(voice => (
              <option key={voice.voice_id} value={voice.voice_id}>
                {voice.name} {voice.category ? `(${voice.category})` : ''}
              </option>
            ))
          )}
        </select>
        {voices.length === 0 && (
          <p className="text-xs text-amber-600">
            Could not load voices. Using default.
          </p>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex justify-between">
          <label className="text-sm font-medium text-slate-700">Stability</label>
          <span className="text-sm text-slate-500">{settings.stability.toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={settings.stability}
          onChange={(e) => setSettings(s => ({ ...s, stability: parseFloat(e.target.value) }))}
          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
        />
        <p className="text-xs text-slate-500">
          Higher values make the voice more consistent, lower values make it more varied.
        </p>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between">
          <label className="text-sm font-medium text-slate-700">Similarity Boost</label>
          <span className="text-sm text-slate-500">{settings.similarity_boost.toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={settings.similarity_boost}
          onChange={(e) => setSettings(s => ({ ...s, similarity_boost: parseFloat(e.target.value) }))}
          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
        />
        <p className="text-xs text-slate-500">
          Higher values make the voice more similar to the original, but may increase latency.
        </p>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between">
          <label className="text-sm font-medium text-slate-700">Style</label>
          <span className="text-sm text-slate-500">{settings.style.toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={settings.style}
          onChange={(e) => setSettings(s => ({ ...s, style: parseFloat(e.target.value) }))}
          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
        />
        <p className="text-xs text-slate-500">
          Adjust the speaking style. Higher values are more expressive.
        </p>
      </div>

      <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
        <div>
          <label className="text-sm font-medium text-slate-700">Speaker Boost</label>
          <p className="text-xs text-slate-500 mt-0.5">
            Enhance the clarity and presence of the voice
          </p>
        </div>
        <button
          onClick={() => setSettings(s => ({ ...s, use_speaker_boost: !s.use_speaker_boost }))}
          className={`relative w-12 h-6 rounded-full transition-colors ${
            settings.use_speaker_boost ? 'bg-indigo-600' : 'bg-slate-300'
          }`}
        >
          <div
            className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${
              settings.use_speaker_boost ? 'translate-x-6' : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>

      <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-xl hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
        
        <button
          onClick={handleTest}
          disabled={testing}
          className="px-6 py-2.5 bg-white text-slate-700 font-semibold rounded-xl border border-slate-200 hover:bg-slate-50 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {testing ? (
            <>
              <div className="w-4 h-4 border-2 border-slate-400 border-t-transparent rounded-full animate-spin" />
              Testing...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
              </svg>
              Test Voice
            </>
          )}
        </button>

        {hasChanges && (
          <button
            onClick={handleReset}
            className="px-4 py-2.5 text-slate-500 font-medium hover:text-slate-700 transition-colors"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
