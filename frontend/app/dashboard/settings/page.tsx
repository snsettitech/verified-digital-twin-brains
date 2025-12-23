'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

export default function SettingsPage() {
  const [twinId, setTwinId] = useState('eeeed554-9180-4229-a9af-0f8dd2c69e9b');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [twinData, setTwinData] = useState({
    name: '',
    description: '',
    specialization_id: 'vanilla', // Default
    settings: {
      system_prompt: ''
    }
  });

  const fetchTwinData = async () => {
    try {
      const response = await fetch(`http://localhost:8000/twins/${twinId}`, {
        headers: { 'Authorization': 'Bearer development_token' }
      });
      if (response.ok) {
        const data = await response.json();
        setTwinData({
          name: data.name || '',
          description: data.description || '',
          specialization_id: data.specialization_id || 'vanilla',
          settings: {
            system_prompt: data.settings?.system_prompt || ''
          }
        });
      }
    } catch (error) {
      console.error('Error fetching twin data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTwinData();
  }, [twinId]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const response = await fetch(`http://localhost:8000/twins/${twinId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer development_token'
        },
        body: JSON.stringify(twinData)
      });

      if (response.ok) {
        alert('Twin settings updated successfully!');
      } else {
        const error = await response.json();
        alert(`Update failed: ${error.detail || 'Server error'}`);
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('Failed to connect to backend.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-[#f8fafc] text-slate-900 font-sans">
      <header className="sticky top-0 z-10 bg-white border-b px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/dashboard" className="text-xl font-black tracking-tighter text-blue-600 hover:opacity-80 transition-opacity">
            VT-BRAIN
          </Link>
          <nav className="hidden md:flex items-center gap-6">
            <Link href="/dashboard" className="text-sm font-medium text-slate-500 hover:text-slate-800">Chat</Link>
            <a href="#" className="text-sm font-medium text-slate-500 hover:text-slate-800">Knowledge Base</a>
            <Link href="/dashboard/escalations" className="text-sm font-medium text-slate-500 hover:text-slate-800">Escalations</Link>
            <Link href="/dashboard/settings" className="text-sm font-bold text-blue-600 border-b-2 border-blue-600 pb-1">Settings</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full p-10">
        <h1 className="text-3xl font-extrabold tracking-tight mb-8">Twin Settings</h1>

        {loading ? (
          <div className="flex justify-center p-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <form onSubmit={handleSave} className="bg-white p-8 rounded-3xl border border-slate-100 shadow-sm space-y-6">
            <div>
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 block">Twin Name</label>
              <input
                type="text"
                className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                value={twinData.name}
                onChange={(e) => setTwinData({ ...twinData, name: e.target.value })}
                placeholder="e.g., Personal Assistant Twin"
              />
            </div>

            <div>
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 block">Description</label>
              <textarea
                className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none"
                rows={2}
                value={twinData.description}
                onChange={(e) => setTwinData({ ...twinData, description: e.target.value })}
                placeholder="Briefly describe what this twin represents..."
              />
            </div>

            <div>
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 block">System Prompt (Personality)</label>
              <textarea
                className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all resize-none"
                rows={8}
                value={twinData.settings.system_prompt}
                onChange={(e) => setTwinData({
                  ...twinData,
                  settings: { ...twinData.settings, system_prompt: e.target.value }
                })}
                placeholder="Define how your twin should behave and respond..."
              />
              <p className="text-[10px] text-slate-400 mt-2 italic">
                Tip: Describe the twin's tone, expertise level, and any specific constraints.
              </p>
            </div>

            {/* Cognitive Engine Selector (Gate 1 Premium UI) */}
            <div className="pt-6 border-t border-slate-100">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4 block">
                Cognitive Engine Specialization
              </label>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Vanilla Card */}
                <div
                  onClick={() => setTwinData({ ...twinData, specialization_id: 'vanilla' })}
                  className={`relative p-5 rounded-2xl border-2 cursor-pointer transition-all hover:shadow-md ${twinData.specialization_id === 'vanilla'
                    ? 'border-blue-600 bg-blue-50/50'
                    : 'border-slate-100 bg-white hover:border-slate-300'
                    }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="h-8 w-8 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                    </div>
                    {twinData.specialization_id === 'vanilla' && (
                      <span className="bg-blue-600 text-white text-[10px] font-bold px-2 py-1 rounded-full">ACTIVE</span>
                    )}
                  </div>
                  <h3 className="font-bold text-slate-800">Vanilla Brain</h3>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                    Standard RAG engine with vector memory. Best for general Q&A and document retrieval tasks.
                  </p>
                </div>

                {/* VC Brain Card */}
                <div
                  onClick={() => setTwinData({ ...twinData, specialization_id: 'vc' })}
                  className={`relative p-5 rounded-2xl border-2 cursor-pointer transition-all hover:shadow-md ${twinData.specialization_id === 'vc'
                    ? 'border-purple-600 bg-purple-50/50'
                    : 'border-slate-100 bg-white hover:border-slate-300'
                    }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="h-8 w-8 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                    </div>
                    {twinData.specialization_id === 'vc' && (
                      <span className="bg-purple-600 text-white text-[10px] font-bold px-2 py-1 rounded-full">ACTIVE</span>
                    )}
                  </div>
                  <h3 className="font-bold text-slate-800">VC Brain</h3>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                    Specialized engine with Graph Memory and Interview protocols. Designed for deal flow and founder vetting.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                type="submit"
                disabled={saving}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white text-xs font-bold py-3 px-10 rounded-xl transition-all shadow-md shadow-blue-100 flex items-center gap-2"
              >
                {saving ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    Saving Changes...
                  </>
                ) : 'Update Twin Memory'}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
