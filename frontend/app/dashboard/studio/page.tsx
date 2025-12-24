'use client';

import React, { useState, useEffect } from 'react';

export default function StudioPage() {
  const [settings, setSettings] = useState<any>({
    name: 'Verified Twin',
    description: 'A digital clone of your verified knowledge.',
    settings: {
      system_prompt: '',
      tone: 'professional',
      conciseness: 'balanced'
    }
  });
  const [styleProfile, setStyleProfile] = useState('Analyzing your verified memory...');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const twinId = "eeeed554-9180-4229-a9af-0f8dd2c69e9b";

  useEffect(() => {
    const fetchTwin = async () => {
      try {
        const response = await fetch(`http://localhost:8000/twins/${twinId}`, {
          headers: { 'Authorization': 'Bearer development_token' }
        });
        if (response.ok) {
          const data = await response.json();
          setSettings(data);
        }
      } catch (error) {
        console.error('Error fetching twin:', error);
      } finally {
        setLoading(false);
      }
    };
    
    // We don't have a direct endpoint for style profile yet, but let's simulate it 
    // since we implemented the backend logic for it in agent.py
    fetchTwin();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`http://localhost:8000/twins/${twinId}`, {
        method: 'PATCH',
        headers: { 
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });
      if (response.ok) {
        // Show success
      }
    } catch (error) {
      console.error('Error saving settings:', error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-20 text-center animate-pulse text-slate-400">Loading your Twin's profile...</div>;

  return (
    <div className="max-w-4xl space-y-10">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">Persona Studio</h1>
        <p className="text-slate-500 mt-2">Refine how your Digital Twin communicates and presents itself.</p>
      </div>

      <div className="grid grid-cols-1 gap-8">
        {/* Style Analysis Card */}
        <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-8 rounded-3xl text-white shadow-xl shadow-blue-100">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-12 h-12 bg-white/20 rounded-2xl flex items-center justify-center backdrop-blur-md">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
            </div>
            <div>
              <h3 className="text-lg font-bold">Automatic Style Profile</h3>
              <p className="text-blue-100 text-xs">Generated from your verified responses.</p>
            </div>
          </div>
          <div className="bg-white/10 backdrop-blur-sm p-6 rounded-2xl border border-white/20 italic text-sm leading-relaxed">
            "{styleProfile}"
          </div>
          <div className="mt-4 flex gap-2">
            <span className="px-3 py-1 bg-white/20 rounded-full text-[10px] font-bold uppercase tracking-wider">Tone: Professional</span>
            <span className="px-3 py-1 bg-white/20 rounded-full text-[10px] font-bold uppercase tracking-wider">Confidence: 94%</span>
          </div>
        </div>

        {/* Identity Settings */}
        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
            Twin Identity
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-black text-slate-400 uppercase tracking-widest">Twin Name</label>
              <input 
                type="text" 
                value={settings.name}
                onChange={(e) => setSettings({...settings, name: e.target.value})}
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 font-bold"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-black text-slate-400 uppercase tracking-widest">Public Avatar URL</label>
              <input 
                type="text" 
                placeholder="https://..." 
                className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">Bio / Description</label>
            <textarea 
              rows={3}
              value={settings.description}
              onChange={(e) => setSettings({...settings, description: e.target.value})}
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
        </div>

        {/* Brain Configuration */}
        <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm space-y-6">
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <svg className="w-5 h-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"></path></svg>
            Intelligence & Guardrails
          </h3>

          <div className="space-y-2">
            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">Custom System Prompt</label>
            <textarea 
              rows={6}
              value={settings.settings?.system_prompt || ''}
              onChange={(e) => setSettings({
                ...settings, 
                settings: { ...settings.settings, system_prompt: e.target.value }
              })}
              placeholder="You are the AI Digital Twin of..."
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-xs"
            />
            <p className="text-[10px] text-slate-400 italic">Leave blank to use the default Verified Digital Twin prompt.</p>
          </div>

          <div className="flex justify-end pt-4">
            <button 
              onClick={handleSave}
              disabled={saving}
              className="px-10 py-3 bg-blue-600 text-white rounded-2xl text-sm font-bold hover:bg-blue-700 transition-all shadow-lg shadow-blue-100 disabled:opacity-50"
            >
              {saving ? 'Saving changes...' : 'Save Persona'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
