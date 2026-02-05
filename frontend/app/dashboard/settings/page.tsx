'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { getSupabaseClient } from '@/lib/supabase/client';
import { useTwin } from '@/lib/context/TwinContext';
import DeleteTwinModal from '@/components/ui/DeleteTwinModal';
import { useToast } from '@/components/ui';

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
  const { activeTwin, user, refreshTwins, isLoading: twinLoading, clearActiveTwin } = useTwin();
  const supabase = getSupabaseClient();
  const { showToast } = useToast();

  const [activeTab, setActiveTab] = useState<'profile' | 'twin' | 'billing' | 'danger'>('profile');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [twinActionLoading, setTwinActionLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const router = useRouter();

  // Empty defaults - will be populated from activeTwin
  const [profile, setProfile] = useState<UserProfile>({
    name: '',
    email: '',
    avatarUrl: ''
  });

  // Password change state
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  // Photo upload
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);

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

  // Handle photo upload
  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file
    if (!file.type.startsWith('image/')) {
      showToast('Please select an image file', 'error');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast('Image must be under 5MB', 'error');
      return;
    }

    setUploadingPhoto(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.user) {
        showToast('Not authenticated', 'error');
        return;
      }

      const userId = session.user.id;
      const fileExt = file.name.split('.').pop();
      const filePath = `avatars/${userId}.${fileExt}`;

      // Upload to Supabase Storage
      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(filePath, file, { upsert: true });

      if (uploadError) {
        console.error('[Settings] Upload error:', uploadError);
        showToast('Upload failed. Storage may not be configured.', 'error');
        return;
      }

      // Get public URL
      const { data: { publicUrl } } = supabase.storage
        .from('avatars')
        .getPublicUrl(filePath);

      // Update profile state
      setProfile(prev => ({ ...prev, avatarUrl: publicUrl }));
      showToast('Photo uploaded', 'success');
    } catch (err) {
      console.error('[Settings] Photo upload error:', err);
      showToast('Failed to upload photo', 'error');
    } finally {
      setUploadingPhoto(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Handle password change
  const handlePasswordChange = async () => {
    if (!newPassword.trim()) {
      showToast('Please enter a new password', 'error');
      return;
    }
    if (newPassword.length < 6) {
      showToast('Password must be at least 6 characters', 'error');
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast('Passwords do not match', 'error');
      return;
    }

    setChangingPassword(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) {
        console.error('[Settings] Password change error:', error);
        showToast(error.message || 'Failed to change password', 'error');
        return;
      }
      showToast('Password changed successfully', 'success');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      console.error('[Settings] Password error:', err);
      showToast('Failed to change password', 'error');
    } finally {
      setChangingPassword(false);
    }
  };

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
        showToast('Settings saved', 'success');
      } else {
        const errText = await response.text();
        console.error('[Settings] Save failed:', errText);
        showToast('Failed to save settings', 'error');
      }
    } catch (error) {
      console.error('[Settings] Error saving:', error);
      showToast('Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  // Delete twin handler
  const handleDeleteTwin = async (permanent: boolean): Promise<void> => {
    if (!activeTwin) throw new Error('No active twin');
    setTwinActionLoading(true);

    try {
      const token = await getAuthToken();
      if (!token) throw new Error('Not authenticated');

      // Use archive endpoint for soft delete, DELETE with ?hard=true for permanent
      const url = permanent
        ? `${API_URL}/twins/${activeTwin.id}?hard=true`
        : `${API_URL}/twins/${activeTwin.id}/archive`;
      const method = permanent ? 'DELETE' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        showToast(errorData.detail || 'Failed to delete twin', 'error');
        throw new Error(errorData.detail || 'Failed to delete twin');
      }

      console.log('[Settings] Twin deleted successfully, refreshing...');
      await refreshTwins({ allowEmpty: true });
      clearActiveTwin();
      showToast(permanent ? 'Twin permanently deleted' : 'Twin archived', 'success');
      router.push('/dashboard');
    } finally {
      setTwinActionLoading(false);
    }
  };

  // Export twin handler
  const handleExportTwin = async () => {
    if (!activeTwin) {
      showToast('No twin selected', 'warning');
      return;
    }

    try {
      setExporting(true);
      const token = await getAuthToken();
      if (!token) {
        showToast('Not authenticated', 'error');
        return;
      }

      const response = await fetch(`${API_URL}/twins/${activeTwin.id}/export`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        showToast(`Export failed: ${errorData.detail}`, 'error');
        return;
      }

      // Trigger download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `twin_${activeTwin.id}_export.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      console.log('[Settings] Twin exported successfully');
      showToast('Twin export downloaded', 'success');
    } catch (error) {
      console.error('[Settings] Export error:', error);
      showToast('Failed to export twin', 'error');
    } finally {
      setExporting(false);
    }
  };

  // Delete account handler
  const [showDeleteAccountModal, setShowDeleteAccountModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deletingAccount, setDeletingAccount] = useState(false);

  const handleDeleteAccount = async () => {
    if (deleteConfirmation !== 'DELETE' && deleteConfirmation !== user?.email) {
      showToast('Please type DELETE or your email to confirm', 'warning');
      return;
    }

    setDeletingAccount(true);
    try {
      const token = await getAuthToken();
      if (!token) {
        showToast('Not authenticated', 'error');
        return;
      }

      const response = await fetch(`${API_URL}/account/delete`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ confirmation: deleteConfirmation })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        showToast(`Account deletion failed: ${errorData.detail}`, 'error');
        return;
      }

      // Show success before signing out + redirecting
      showToast('Account deleted', 'success');
      await new Promise((resolve) => setTimeout(resolve, 400));
      await supabase.auth.signOut();
      clearActiveTwin();
      router.push('/');
    } catch (error) {
      console.error('[Settings] Delete account error:', error);
      showToast('Failed to delete account', 'error');
    } finally {
      setDeletingAccount(false);
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
            <div className="w-20 h-20 rounded-full flex items-center justify-center text-2xl font-bold text-white overflow-hidden">
              {profile.avatarUrl ? (
                <img src={profile.avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                  {profile.name.split(' ').map(n => n[0]).join('')}
                </div>
              )}
            </div>
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handlePhotoUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingPhoto}
                className="px-4 py-2 bg-slate-100 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-200 transition-colors disabled:opacity-50"
              >
                {uploadingPhoto ? 'Uploading...' : 'Upload Photo'}
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
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>
            </div>
            <button
              onClick={handlePasswordChange}
              disabled={changingPassword || !newPassword.trim()}
              className="mt-4 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50"
            >
              {changingPassword ? 'Updating...' : 'Update Password'}
            </button>
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
                <p className="text-sm text-slate-500">Download all your twin&apos;s data</p>
              </div>
              <button
                onClick={handleExportTwin}
                disabled={!activeTwin || exporting}
                className="px-4 py-2 border border-slate-200 text-slate-700 font-medium text-sm rounded-xl hover:bg-slate-50 transition-colors disabled:opacity-50"
              >
                {exporting ? 'Exporting...' : 'Export'}
              </button>
            </div>
            <div className="p-4 border border-red-200 rounded-xl flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">Delete Twin</p>
                <p className="text-sm text-slate-500">Archive or permanently delete your digital twin</p>
              </div>
              <button
                onClick={() => setShowDeleteModal(true)}
                disabled={!activeTwin || twinActionLoading}
                className="px-4 py-2 bg-red-500 text-white font-medium text-sm rounded-xl hover:bg-red-600 transition-colors disabled:opacity-50"
              >
                {twinActionLoading ? 'Working...' : 'Delete'}
              </button>
            </div>
            <div className="p-4 border border-red-200 rounded-xl flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">Delete Account</p>
                <p className="text-sm text-slate-500">Permanently delete your account and all data</p>
              </div>
              <button
                onClick={() => setShowDeleteAccountModal(true)}
                className="px-4 py-2 bg-red-600 text-white font-medium text-sm rounded-xl hover:bg-red-700 transition-colors"
              >
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

      {/* Delete Twin Modal */}
      <DeleteTwinModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onDelete={handleDeleteTwin}
        twinName={activeTwin?.name || ''}
        twinHandle={(activeTwin?.settings as any)?.handle || ''}
        twinId={activeTwin?.id || ''}
      />

      {/* Delete Account Modal */}
      {showDeleteAccountModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full mx-4 shadow-xl">
            <h2 className="text-xl font-bold text-red-600 mb-2">Delete Account</h2>
            <p className="text-slate-600 mb-4">
              This will permanently delete your account and archive all your twins. This action cannot be undone.
            </p>
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <p className="text-sm text-red-700">
                <strong>Warning:</strong> All your twins, data, and settings will be lost.
              </p>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Type <strong>DELETE</strong> or your email to confirm:
              </label>
              <input
                type="text"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                placeholder="DELETE"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowDeleteAccountModal(false);
                  setDeleteConfirmation('');
                }}
                className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deletingAccount || (deleteConfirmation !== 'DELETE' && deleteConfirmation !== user?.email)}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deletingAccount ? 'Deleting...' : 'Delete Account'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

