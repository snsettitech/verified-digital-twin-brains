'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface ContentPermission {
  id: string;
  content_type: string;
  content_id: string;
}

interface Source {
  id: string;
  filename: string;
  status: string;
}

interface VerifiedQnA {
  id: string;
  question: string;
  answer: string;
}

export default function GroupContentPage() {
  const params = useParams();
  const router = useRouter();
  const { get, post, del } = useAuthFetch();
  const groupId = params.group_id as string;

  const [permissions, setPermissions] = useState<ContentPermission[]>([]);
  const [loading, setLoading] = useState(true);
  const [contentType, setContentType] = useState<'source' | 'verified_qna'>('source');
  const [sources, setSources] = useState<Source[]>([]);
  const [verifiedQnA, setVerifiedQnA] = useState<VerifiedQnA[]>([]);
  const [selectedContentIds, setSelectedContentIds] = useState<string[]>([]);
  const [granting, setGranting] = useState(false);
  const [twinId, setTwinId] = useState<string>('');

  const fetchGroupInfo = useCallback(async () => {
    try {
      const response = await get(`/access-groups/${groupId}`);
      if (response.ok) {
        const group = await response.json();
        setTwinId(group.twin_id);
      }
    } catch (error) {
      console.error('Error fetching group info:', error);
    }
  }, [groupId, get]);

  const fetchPermissions = useCallback(async () => {
    try {
      const response = await get(`/access-groups/${groupId}/permissions`);
      if (response.ok) {
        const data = await response.json();
        setPermissions(data);
      }
    } catch (error) {
      console.error('Error fetching permissions:', error);
    } finally {
      setLoading(false);
    }
  }, [groupId, get]);

  const fetchSources = useCallback(async () => {
    if (!twinId) return;

    try {
      const response = await get(`/sources/${twinId}`);
      if (response.ok) {
        const data = await response.json();
        setSources(data);
      }
    } catch (error) {
      console.error('Error fetching sources:', error);
    }
  }, [twinId, get]);

  const fetchVerifiedQnA = useCallback(async () => {
    if (!twinId) return;

    try {
      const response = await get(`/twins/${twinId}/verified-qna`);
      if (response.ok) {
        const data = await response.json();
        setVerifiedQnA(data);
      }
    } catch (error) {
      console.error('Error fetching verified QnA:', error);
    }
  }, [twinId, get]);

  useEffect(() => {
    fetchPermissions();
    fetchGroupInfo();
  }, [fetchPermissions, fetchGroupInfo]);

  useEffect(() => {
    if (twinId) {
      if (contentType === 'source') {
        fetchSources();
      } else {
        fetchVerifiedQnA();
      }
    }
  }, [contentType, twinId, fetchSources, fetchVerifiedQnA]);

  const handleGrantAccess = async () => {
    if (selectedContentIds.length === 0) return;

    setGranting(true);
    try {
      const response = await post(`/access-groups/${groupId}/permissions`, {
        content_type: contentType,
        content_ids: selectedContentIds
      });

      if (response.ok) {
        setSelectedContentIds([]);
        fetchPermissions();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to grant access'}`);
      }
    } catch (error) {
      console.error('Error granting access:', error);
      alert('Failed to grant access');
    } finally {
      setGranting(false);
    }
  };

  const handleRevokeAccess = async (contentType: string, contentId: string) => {
    if (!confirm('Are you sure you want to revoke access to this content?')) {
      return;
    }

    try {
      const response = await del(`/access-groups/${groupId}/permissions/${contentType}/${contentId}`);

      if (response.ok) {
        fetchPermissions();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to revoke access'}`);
      }
    } catch (error) {
      console.error('Error revoking access:', error);
      alert('Failed to revoke access');
    }
  };

  const hasPermission = (contentId: string) => {
    return permissions.some(
      p => p.content_type === contentType && p.content_id === contentId
    );
  };

  const toggleContentSelection = (contentId: string) => {
    if (selectedContentIds.includes(contentId)) {
      setSelectedContentIds(selectedContentIds.filter(id => id !== contentId));
    } else {
      setSelectedContentIds([...selectedContentIds, contentId]);
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  const currentPermissions = permissions.filter(p => p.content_type === contentType);
  const availableContent = contentType === 'source' ? sources : verifiedQnA;

  return (
    <div className="p-8">
      <div className="mb-6">
        <button
          onClick={() => router.back()}
          className="text-blue-600 hover:underline mb-2"
        >
          ← Back to Groups
        </button>
        <h1 className="text-3xl font-bold mb-4">Manage Content Access</h1>

        <div className="flex gap-4 mb-4">
          <button
            onClick={() => setContentType('source')}
            className={`px-4 py-2 rounded-lg ${contentType === 'source'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
          >
            Sources
          </button>
          <button
            onClick={() => setContentType('verified_qna')}
            className={`px-4 py-2 rounded-lg ${contentType === 'verified_qna'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
          >
            Verified QnA
          </button>
        </div>
      </div>

      <div className="mb-4">
        <h2 className="text-xl font-semibold mb-2">Grant Access to New Content</h2>
        <div className="border border-gray-200 rounded-lg p-4 max-h-64 overflow-y-auto">
          {availableContent.length === 0 ? (
            <p className="text-gray-500">No {contentType} content available.</p>
          ) : (
            availableContent.map((item) => {
              const hasAccess = hasPermission(item.id);
              if (hasAccess) return null; // Don't show items that already have access

              return (
                <label
                  key={item.id}
                  className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedContentIds.includes(item.id)}
                    onChange={() => toggleContentSelection(item.id)}
                  />
                  <span className="flex-1">
                    {contentType === 'source' ? (item as Source).filename : (item as VerifiedQnA).question}
                  </span>
                </label>
              );
            })
          )}
        </div>
        {selectedContentIds.length > 0 && (
          <button
            onClick={handleGrantAccess}
            className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            disabled={granting}
          >
            {granting ? 'Granting...' : `Grant Access to ${selectedContentIds.length} Item(s)`}
          </button>
        )}
      </div>

      <div>
        <h2 className="text-xl font-semibold mb-2">Current Permissions ({currentPermissions.length})</h2>
        <div className="space-y-2">
          {currentPermissions.length === 0 ? (
            <p className="text-gray-500">No {contentType} content has access yet.</p>
          ) : (
            currentPermissions.map((permission) => {
              const content = availableContent.find(item => item.id === permission.content_id);
              if (!content) return null;

              return (
                <div
                  key={permission.id}
                  className="border border-gray-200 rounded-lg p-4 flex justify-between items-center"
                >
                  <div>
                    {contentType === 'source' ? (content as Source).filename : (content as VerifiedQnA).question}
                  </div>
                  <button
                    onClick={() => handleRevokeAccess(permission.content_type, permission.content_id)}
                    className="px-3 py-1 text-red-600 hover:bg-red-50 rounded"
                  >
                    Revoke
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
