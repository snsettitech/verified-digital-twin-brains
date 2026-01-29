'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { getSupabaseClient } from '@/lib/supabase/client';
import { useTwin } from '@/lib/context/TwinContext';

interface UserProfile {
  name: string;
  email: string;
  avatarUrl: string;
}

interface TwinSettings {
  name: string;
  handle: string;
  tagline: string;
  tone: string;
  responseLength: string;
  firstPerson: boolean;
  systemPrompt: string;
}

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function SettingsPage() {
  const { activeTwin, user, refreshTwins, isLoading: twinLoading } = useTwin();
  const supabase = getSupabaseClient();

  const [activeTab, setActiveTab] = useState<'profile' | 'twin' | 'billing' | 'danger'>('profile');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  // Empty defaults - will be populated from activeTwin
  const [profile, setProfile] = useState<UserProfile>({
    name: '',
    email: '',
    avatarUrl: ''
  });

  // Empty defaults - will be populated from activeTwin.settings
  const [twinSettings, setTwinSettings] = useState<TwinSettings>({
    name: '',
    handle: '',
    tagline: '',
    tone: 'friendly',
    responseLength: 'balanced',
    firstPerson: true,
    systemPrompt: ''
  });

  // Get auth token
  const getAuthToken = useCallback(async () => {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token;
  }, [supabase]);

  // Initialize from activeTwin when it changes
  useEffect(() => {
    if (activeTwin) {
      const settings = (activeTwin.settings || {}) as Record<string, unknown>;
      const personality = (settings.personality || {}) as Record<string, unknown>;

      setTwinSettings({
        name: activeTwin.name || '',
        handle: (settings.handle as string) || '',
        tagline: (settings.tagline as string) || '',
        tone: (personality.tone as string) || 'friendly',
        responseLength: (personality.responseLength as string) || 'balanced',
        firstPerson: personality.firstPerson !== false,
        systemPrompt: (settings.system_prompt as string) || ''
      });
      setSettingsLoaded(true);
      console.log('[Settings] Loaded from activeTwin:', activeTwin.id);
    }
  }, [activeTwin?.id]); // Re-run when twin switches

  // Initialize profile from user
  useEffect(() => {
    if (user) {
      setProfile({
        name: user.full_name || '',
        email: user.email || '',
        avatarUrl: user.avatar_url || ''
      });
    }
  }, [user]);

  // Real PATCH save with TwinContext refresh
  const handleSave = async () => {
    if (!activeTwin) return;

    setSaving(true);
    try {
      const token = await getAuthToken();
      if (!token) {
        console.error('[Settings] No auth token');
        return;
      }

      const response = await fetch(`${API_URL}/twins/${activeTwin.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: twinSettings.name,
          settings: {
            handle: twinSettings.handle,
            tagline: twinSettings.tagline,
            system_prompt: twinSettings.systemPrompt,
            personality: {
              tone: twinSettings.tone,
              responseLength: twinSettings.responseLength,
              firstPerson: twinSettings.firstPerson
            }
          }
        })
      });

      if (response.ok) {
        console.log('[Settings] Saved successfully, refreshing twins...');
        // Refresh TwinContext so header + other pages reflect changes
        await refreshTwins();
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        console.error('[Settings] Save failed:', await response.text());
      }
    } catch (error) {
      console.error('[Settings] Error saving:', error);
    } finally {
      setSaving(false);
    }
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: '👤' },
    { id: 'twin', label: 'Twin Settings', icon: '🤖' },
    { id: 'billing', label: 'Billing', icon: '💳' },
    { id: 'danger', label: 'Danger Zone', icon: '⚠️' },
  ];

  // Loading state
  if (twinLoading || (activeTab === 'twin' && !settingsLoaded && activeTwin)) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-slate-500">Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-black tracking-tight text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Manage your account and twin configuration</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.id
              ? 'border-indigo-600 text-indigo-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          <h2 className="text-lg font-bold text-slate-900">Your Profile</h2>

          {/* Avatar */}
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center text-2xl font-bold text-white">
              {profile.name.split(' ').map(n => n[0]).join('')}
            </div>
            <div>
              <button className="px-4 py-2 bg-slate-100 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-200 transition-colors">
                Upload Photo
              </button>
              <p className="text-xs text-slate-400 mt-2">JPG, PNG up to 5MB</p>
            </div>
          </div>

          {/* Form */}
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Full Name</label>
              <input
                type="text"
                value={profile.name}
                onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Email</label>
              <input
                type="email"
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Password */}
          <div className="pt-6 border-t border-slate-100">
            <h3 className="font-semibold text-slate-900 mb-4">Change Password</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">New Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Confirm Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Twin Settings Tab */}
      {activeTab === 'twin' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          <h2 className="text-lg font-bold text-slate-900">Twin Configuration</h2>

          {/* Basic Info */}
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Twin Name</label>
              <input
                type="text"
                value={twinSettings.name}
                onChange={(e) => setTwinSettings({ ...twinSettings, name: e.target.value })}
                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Handle</label>
              <div className="flex">
                <span className="px-4 py-3 bg-slate-100 border border-r-0 border-slate-200 rounded-l-xl text-slate-500">@</span>
                <input
                  type="text"
                  value={twinSettings.handle}
                  onChange={(e) => setTwinSettings({ ...twinSettings, handle: e.target.value })}
                  className="flex-1 px-4 py-3 border border-slate-200 rounded-r-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-2">Tagline</label>
              <input
                type="text"
                value={twinSettings.tagline}
                onChange={(e) => setTwinSettings({ ...twinSettings, tagline: e.target.value })}
                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Personality */}
          <div className="pt-6 border-t border-slate-100">
            <h3 className="font-semibold text-slate-900 mb-4">Personality</h3>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Tone</label>
                <select
                  value={twinSettings.tone}
                  onChange={(e) => setTwinSettings({ ...twinSettings, tone: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="professional">Professional</option>
                  <option value="friendly">Friendly</option>
                  <option value="casual">Casual</option>
                  <option value="technical">Technical</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Response Length</label>
                <select
                  value={twinSettings.responseLength}
                  onChange={(e) => setTwinSettings({ ...twinSettings, responseLength: e.target.value })}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="concise">Concise</option>
                  <option value="balanced">Balanced</option>
                  <option value="detailed">Detailed</option>
                </select>
              </div>
            </div>

            {/* First Person Toggle */}
            <div className="mt-4 flex items-center justify-between p-4 bg-slate-50 rounded-xl">
              <div>
                <p className="font-medium text-slate-900">Speak as "I"</p>
                <p className="text-sm text-slate-500">Use first person pronouns</p>
              </div>
              <button
                onClick={() => setTwinSettings({ ...twinSettings, firstPerson: !twinSettings.firstPerson })}
                className={`w-12 h-6 rounded-full transition-colors ${twinSettings.firstPerson ? 'bg-indigo-600' : 'bg-slate-300'
                  }`}
              >
                <div className={`w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${twinSettings.firstPerson ? 'translate-x-6' : 'translate-x-0.5'
                  }`} />
              </button>
            </div>
          </div>

          {/* System Prompt */}
          <div className="pt-6 border-t border-slate-100">
            <h3 className="font-semibold text-slate-900 mb-4">System Prompt</h3>
            <textarea
              value={twinSettings.systemPrompt}
              onChange={(e) => setTwinSettings({ ...twinSettings, systemPrompt: e.target.value })}
              rows={4}
              className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
            />
            <p className="text-xs text-slate-400 mt-2">This prompt guides how your twin responds</p>
          </div>
        </div>
      )}

      {/* Billing Tab */}
      {activeTab === 'billing' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
          <h2 className="text-lg font-bold text-slate-900">Billing & Subscription</h2>

          {/* Current Plan */}
          <div className="p-6 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-2xl text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-indigo-200 text-sm font-medium">Current Plan</p>
                <p className="text-2xl font-black mt-1">Free Plan</p>
              </div>
              <button className="px-4 py-2 bg-white text-indigo-600 font-semibold text-sm rounded-xl hover:bg-indigo-50 transition-colors">
                Upgrade to Pro
              </button>
            </div>
            <div className="mt-4 pt-4 border-t border-white/20">
              <div className="flex justify-between text-sm">
                <span className="text-indigo-200">Messages used</span>
                <span className="font-medium">67 / 100</span>
              </div>
              <div className="mt-2 w-full h-2 bg-white/20 rounded-full overflow-hidden">
                <div className="h-full bg-white rounded-full" style={{ width: '67%' }} />
              </div>
            </div>
          </div>

          {/* Plan Comparison */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="p-4 border border-slate-200 rounded-xl">
              <p className="font-bold text-slate-900">Pro Plan</p>
              <p className="text-2xl font-black text-slate-900 mt-2">$29<span className="text-sm font-normal text-slate-400">/month</span></p>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                <li className="flex items-center gap-2">✓ Unlimited messages</li>
                <li className="flex items-center gap-2">✓ Custom branding</li>
                <li className="flex items-center gap-2">✓ API access</li>
                <li className="flex items-center gap-2">✓ Priority support</li>
              </ul>
            </div>
            <div className="p-4 border border-slate-200 rounded-xl">
              <p className="font-bold text-slate-900">Enterprise</p>
              <p className="text-2xl font-black text-slate-900 mt-2">Custom</p>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                <li className="flex items-center gap-2">✓ Everything in Pro</li>
                <li className="flex items-center gap-2">✓ SSO/SAML</li>
                <li className="flex items-center gap-2">✓ SLA guarantee</li>
                <li className="flex items-center gap-2">✓ Dedicated support</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Danger Zone Tab */}
      {activeTab === 'danger' && (
        <div className="bg-white rounded-2xl border border-red-200 shadow-sm p-6 space-y-6">
          <h2 className="text-lg font-bold text-red-600">Danger Zone</h2>
          <p className="text-slate-600">These actions are permanent and cannot be undone.</p>

          <div className="space-y-4">
            <div className="p-4 border border-red-200 rounded-xl flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">Export Data</p>
                <p className="text-sm text-slate-500">Download all your twin's data</p>
              </div>
              <button className="px-4 py-2 border border-slate-200 text-slate-700 font-medium text-sm rounded-xl hover:bg-slate-50 transition-colors">
                Export
              </button>
            </div>
            <div className="p-4 border border-red-200 rounded-xl flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">Delete Twin</p>
                <p className="text-sm text-slate-500">Permanently delete your digital twin</p>
              </div>
              <button className="px-4 py-2 bg-red-500 text-white font-medium text-sm rounded-xl hover:bg-red-600 transition-colors">
                Delete
              </button>
            </div>
            <div className="p-4 border border-red-200 rounded-xl flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">Delete Account</p>
                <p className="text-sm text-slate-500">Permanently delete your account and all data</p>
              </div>
              <button className="px-4 py-2 bg-red-600 text-white font-medium text-sm rounded-xl hover:bg-red-700 transition-colors">
                Delete Account
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save Button */}
      {(activeTab === 'profile' || activeTab === 'twin') && (
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className={`px-6 py-3 font-semibold text-sm rounded-xl transition-all ${saved
              ? 'bg-emerald-500 text-white'
              : 'bg-slate-900 text-white hover:bg-slate-800'
              } disabled:opacity-50`}
          >
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>
      )}
    </div>
  );
}
