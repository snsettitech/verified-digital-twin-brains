'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const AUTH_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN || 'development_token';
const FRONTEND_URL = process.env.NEXT_PUBLIC_FRONTEND_URL || 'http://localhost:3000';

interface User {
  id: string;
  email: string;
  role: string;
  created_at: string;
  invited_at?: string;
}

const roleColors: Record<string, 'info' | 'warning' | 'success'> = {
  owner: 'info',
  admin: 'warning',
  viewer: 'success',
};

const avatarColors = [
  'from-indigo-400 to-purple-500',
  'from-emerald-400 to-teal-500',
  'from-orange-400 to-red-500',
  'from-pink-400 to-rose-500',
  'from-cyan-400 to-blue-500',
];

function getInitials(email: string): string {
  const parts = email.split('@')[0].split(/[._-]/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return email.slice(0, 2).toUpperCase();
}

function getAvatarColor(email: string): string {
  const hash = email.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return avatarColors[hash % avatarColors.length];
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
  const [inviting, setInviting] = useState(false);
  const [createdInvitation, setCreatedInvitation] = useState<{ url: string; email: string } | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/users`, {
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (error) {
      console.error('Error fetching users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleInviteUser = async () => {
    if (!inviteEmail.trim()) return;

    setInviting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/users/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${AUTH_TOKEN}`
        },
        body: JSON.stringify({
          email: inviteEmail,
          role: inviteRole
        })
      });

      if (response.ok) {
        const data = await response.json();
        setCreatedInvitation({
          url: data.invitation_url,
          email: data.email
        });
        setInviteEmail('');
        setShowInviteModal(false);
        await fetchUsers();
      } else {
        const error = await response.json();
        alert(`Failed to invite user: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error inviting user:', error);
      alert('Failed to invite user');
    } finally {
      setInviting(false);
    }
  };

  const handleUpdateRole = async (userId: string, newRole: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/users/${userId}/role`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${AUTH_TOKEN}`
        },
        body: JSON.stringify({ role: newRole })
      });

      if (response.ok) {
        await fetchUsers();
      } else {
        alert('Failed to update user role');
      }
    } catch (error) {
      console.error('Error updating role:', error);
      alert('Failed to update user role');
    }
  };

  const handleDeleteUser = async (userId: string, email: string) => {
    if (!confirm(`Are you sure you want to remove ${email} from the team? This action cannot be undone.`)) return;

    try {
      const response = await fetch(`${API_BASE_URL}/users/${userId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${AUTH_TOKEN}` }
      });

      if (response.ok) {
        await fetchUsers();
      } else {
        alert('Failed to remove user');
      }
    } catch (error) {
      console.error('Error deleting user:', error);
      alert('Failed to remove user');
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-orange-400 via-pink-500 to-rose-500 p-8 text-white">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-white/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2"></div>
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold">Team</h1>
              <p className="text-white/80 text-sm">Manage your organization members</p>
            </div>
          </div>
          <p className="text-white/70 max-w-xl">
            Invite team members and manage their access levels. Owners have full control, while viewers can only view content.
          </p>
        </div>
        <button
          onClick={() => setShowInviteModal(true)}
          className="absolute top-8 right-8 z-20 px-6 py-2.5 bg-white text-rose-600 rounded-xl font-semibold hover:bg-white/90 transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
        >
          + Invite Member
        </button>
      </div>

      {/* Invitation Success Banner */}
      {createdInvitation && (
        <Card className="border-2 border-emerald-200 bg-gradient-to-r from-emerald-50 to-green-50">
          <CardContent className="py-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center flex-shrink-0">
                <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-emerald-900 mb-1">Invitation Sent!</h3>
                <p className="text-sm text-emerald-700 mb-3">
                  Share this invitation link with <strong>{createdInvitation.email}</strong>:
                </p>
                <div className="flex items-center gap-3">
                  <code className="flex-1 px-4 py-3 bg-white rounded-xl border border-emerald-200 text-sm font-mono text-slate-800 truncate">
                    {createdInvitation.url}
                  </code>
                  <button
                    onClick={() => copyToClipboard(createdInvitation.url)}
                    className={`px-5 py-3 rounded-xl font-semibold transition-all ${copied
                      ? 'bg-emerald-500 text-white'
                      : 'bg-emerald-600 text-white hover:bg-emerald-700'
                      }`}
                  >
                    {copied ? '✓ Copied!' : 'Copy Link'}
                  </button>
                  <button
                    onClick={() => setCreatedInvitation(null)}
                    className="p-3 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-xl transition-all"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Users List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-4 border-rose-200 border-t-rose-600 rounded-full animate-spin"></div>
        </div>
      ) : users.length === 0 ? (
        <Card className="text-center py-16">
          <CardContent>
            <div className="w-24 h-24 bg-gradient-to-br from-orange-100 to-rose-100 rounded-3xl flex items-center justify-center mx-auto mb-6">
              <svg className="w-12 h-12 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">No Team Members Yet</h3>
            <p className="text-slate-500 mb-6 max-w-md mx-auto">
              Start building your team by inviting collaborators to help manage your digital twin.
            </p>
            <button
              onClick={() => setShowInviteModal(true)}
              className="px-6 py-3 bg-gradient-to-r from-orange-400 to-rose-500 text-white rounded-xl font-semibold hover:shadow-lg hover:-translate-y-0.5 transition-all"
            >
              Invite Your First Team Member
            </button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {users.map(user => (
            <Card key={user.id} hover className="group">
              <CardContent className="py-6">
                <div className="flex items-start justify-between mb-4">
                  <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${getAvatarColor(user.email)} flex items-center justify-center text-white font-bold text-lg shadow-lg`}>
                    {getInitials(user.email)}
                  </div>
                  <button
                    onClick={() => handleDeleteUser(user.id, user.email)}
                    className="opacity-0 group-hover:opacity-100 p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                  </button>
                </div>

                <h3 className="font-bold text-slate-900 truncate mb-1">{user.email}</h3>
                <p className="text-sm text-slate-500 mb-4">
                  Joined {new Date(user.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>

                <div className="flex items-center justify-between">
                  <Badge variant={roleColors[user.role] || 'neutral'}>
                    {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                  </Badge>
                  <select
                    value={user.role}
                    onChange={(e) => handleUpdateRole(user.id, e.target.value)}
                    className="text-sm border border-slate-200 rounded-lg px-2 py-1 focus:border-rose-500 focus:ring-0 transition-colors"
                  >
                    <option value="owner">Owner</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Invite Modal */}
      <Modal
        isOpen={showInviteModal}
        onClose={() => setShowInviteModal(false)}
        title="Invite Team Member"
      >
        <div className="space-y-5">
          <div className="text-center pb-4">
            <div className="w-16 h-16 bg-gradient-to-br from-orange-100 to-rose-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"></path>
              </svg>
            </div>
            <p className="text-sm text-slate-500">
              They'll receive an email invitation to join your team.
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Email Address</label>
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-rose-500 focus:ring-0 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-2">Role</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setInviteRole('viewer')}
                className={`p-4 rounded-xl border-2 text-left transition-all ${inviteRole === 'viewer'
                  ? 'border-rose-500 bg-rose-50'
                  : 'border-slate-200 hover:border-slate-300'
                  }`}
              >
                <div className="font-semibold text-slate-900">Viewer</div>
                <div className="text-xs text-slate-500 mt-1">Can view content only</div>
              </button>
              <button
                type="button"
                onClick={() => setInviteRole('owner')}
                className={`p-4 rounded-xl border-2 text-left transition-all ${inviteRole === 'owner'
                  ? 'border-rose-500 bg-rose-50'
                  : 'border-slate-200 hover:border-slate-300'
                  }`}
              >
                <div className="font-semibold text-slate-900">Owner</div>
                <div className="text-xs text-slate-500 mt-1">Full access & control</div>
              </button>
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              onClick={() => setShowInviteModal(false)}
              className="flex-1 px-4 py-3 border-2 border-slate-200 text-slate-700 rounded-xl font-semibold hover:bg-slate-50 transition-colors"
              disabled={inviting}
            >
              Cancel
            </button>
            <button
              onClick={handleInviteUser}
              className="flex-1 px-4 py-3 bg-gradient-to-r from-orange-400 to-rose-500 text-white rounded-xl font-semibold hover:shadow-lg transition-all disabled:opacity-50"
              disabled={inviting || !inviteEmail.trim()}
            >
              {inviting ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Sending...
                </span>
              ) : 'Send Invitation'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
