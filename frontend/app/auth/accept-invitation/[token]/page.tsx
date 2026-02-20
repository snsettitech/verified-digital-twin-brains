'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { API_BASE_URL, API_ENDPOINTS } from '@/lib/constants';
import { getSupabaseClient } from '@/lib/supabase/client';

interface InvitationInfo {
  email: string;
  role: string;
  expires_at?: string;
}

interface AcceptInvitationSession {
  access_token: string;
  refresh_token: string;
}

interface AcceptInvitationApiResponse {
  status: string;
  token?: string;
  session?: AcceptInvitationSession;
}

export default function AcceptInvitationPage() {
  const params = useParams();
  const router = useRouter();
  const token = params?.token as string;
  const supabase = getSupabaseClient();

  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [accepting, setAccepting] = useState(false);
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');

  const validateInvitation = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.AUTH_INVITATION(token)}`);
      if (response.ok) {
        const data = await response.json();
        setInvitation(data);
        setName(data.email.split('@')[0]); // Pre-fill name from email
      } else {
        setError('Invalid or expired invitation link');
      }
    } catch (err) {
      console.error('Error validating invitation:', err);
      setError('Failed to validate invitation');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      validateInvitation();
    }
  }, [token, validateInvitation]);

  const handleAcceptInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim()) {
      setError('Password is required');
      return;
    }

    setAccepting(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}${API_ENDPOINTS.AUTH_ACCEPT_INVITATION}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          token,
          password,
          name: name.trim() || undefined
        })
      });

      if (response.ok) {
        const data: AcceptInvitationApiResponse = await response.json();
        const accessToken = data.session?.access_token || data.token;
        const refreshToken = data.session?.refresh_token;

        if (accessToken && refreshToken) {
          const { error: sessionError } = await supabase.auth.setSession({
            access_token: accessToken,
            refresh_token: refreshToken,
          });
          if (sessionError) {
            setError(sessionError.message || 'Failed to initialize session');
            return;
          }
        }

        // Redirect to dashboard
        router.push('/dashboard');
        router.refresh();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to accept invitation');
      }
    } catch (error) {
      console.error('Error accepting invitation:', error);
      setError('Failed to accept invitation. Please try again.');
    } finally {
      setAccepting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="text-lg text-slate-600">Validating invitation...</div>
        </div>
      </div>
    );
  }

  if (error && !invitation) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 max-w-md w-full">
          <div className="text-center">
            <div className="text-red-600 text-lg font-bold mb-2">Invalid Invitation</div>
            <p className="text-slate-600">{error}</p>
            <button
              onClick={() => router.push('/')}
              className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Go Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 py-12 px-4">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 max-w-md w-full">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">Accept Invitation</h1>
        <p className="text-slate-600 mb-6">
          You&apos;ve been invited to join as <strong>{invitation?.role}</strong>
        </p>

        {invitation && (
          <form onSubmit={handleAcceptInvitation} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Email</label>
              <input
                type="email"
                value={invitation.email}
                disabled
                className="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-lg text-slate-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Name (optional)</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="Choose a password"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-800 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={accepting || !password.trim()}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-slate-300"
            >
              {accepting ? 'Creating Account...' : 'Accept Invitation & Create Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
