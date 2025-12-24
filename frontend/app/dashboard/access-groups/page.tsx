'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

interface AccessGroup {
  id: string;
  name: string;
  description?: string;
  is_default: boolean;
  is_public: boolean;
  created_at: string;
  settings?: any;
}

export default function AccessGroupsPage() {
  const [groups, setGroups] = useState<AccessGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDescription, setNewGroupDescription] = useState('');
  const [newGroupIsPublic, setNewGroupIsPublic] = useState(false);
  const [creating, setCreating] = useState(false);
  const [twinId, setTwinId] = useState<string>('eeeed554-9180-4229-a9af-0f8dd2c69e9b');

  useEffect(() => {
    fetchGroups();
  }, []);

  const fetchGroups = async () => {
    try {
      const response = await fetch(`http://localhost:8000/twins/${twinId}/access-groups`, {
        headers: { 'Authorization': 'Bearer development_token' }
      });
      if (response.ok) {
        const data = await response.json();
        setGroups(data);
      }
    } catch (error) {
      console.error('Error fetching access groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return;
    
    setCreating(true);
    try {
      const response = await fetch(`http://localhost:8000/twins/${twinId}/access-groups`, {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer development_token',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: newGroupName,
          description: newGroupDescription || null,
          is_public: newGroupIsPublic
        })
      });

      if (response.ok) {
        setShowCreateModal(false);
        setNewGroupName('');
        setNewGroupDescription('');
        setNewGroupIsPublic(false);
        fetchGroups();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to create group'}`);
      }
    } catch (error) {
      console.error('Error creating group:', error);
      alert('Failed to create group');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteGroup = async (groupId: string, isDefault: boolean) => {
    if (isDefault) {
      alert('Cannot delete the default group');
      return;
    }
    
    if (!confirm('Are you sure you want to delete this group? This will remove all memberships and permissions.')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/access-groups/${groupId}`, {
        method: 'DELETE',
        headers: { 'Authorization': 'Bearer development_token' }
      });

      if (response.ok) {
        fetchGroups();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to delete group'}`);
      }
    } catch (error) {
      console.error('Error deleting group:', error);
      alert('Failed to delete group');
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Access Groups</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Create Group
        </button>
      </div>

      <div className="space-y-4">
        {groups.map((group) => (
          <div
            key={group.id}
            className="border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h2 className="text-xl font-semibold">{group.name}</h2>
                  {group.is_default && (
                    <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">Default</span>
                  )}
                  {group.is_public && (
                    <span className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded">Public</span>
                  )}
                </div>
                {group.description && (
                  <p className="text-gray-600 mb-3">{group.description}</p>
                )}
                <div className="flex gap-4 text-sm text-gray-500">
                  <Link
                    href={`/dashboard/access-groups/${group.id}/members`}
                    className="text-blue-600 hover:underline"
                  >
                    View Members
                  </Link>
                  <Link
                    href={`/dashboard/access-groups/${group.id}/content`}
                    className="text-blue-600 hover:underline"
                  >
                    Manage Content
                  </Link>
                  <Link
                    href={`/dashboard/access-groups/${group.id}/settings`}
                    className="text-blue-600 hover:underline"
                  >
                    Settings & Limits
                  </Link>
                  <Link
                    href={`/dashboard/access-groups/${group.id}/console`}
                    className="text-blue-600 hover:underline"
                  >
                    Test Console
                  </Link>
                </div>
              </div>
              {!group.is_default && (
                <button
                  onClick={() => handleDeleteGroup(group.id, group.is_default)}
                  className="px-3 py-1 text-red-600 hover:bg-red-50 rounded"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-2xl font-bold mb-4">Create Access Group</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Group Name</label>
                <input
                  type="text"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="e.g., Internal Team, Clients, Public"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description (optional)</label>
                <textarea
                  value={newGroupDescription}
                  onChange={(e) => setNewGroupDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  rows={3}
                  placeholder="Describe this access group..."
                />
              </div>
              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={newGroupIsPublic}
                    onChange={(e) => setNewGroupIsPublic(e.target.checked)}
                  />
                  <span>Public group (for anonymous users)</span>
                </label>
              </div>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                  disabled={creating}
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateGroup}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  disabled={creating || !newGroupName.trim()}
                >
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
