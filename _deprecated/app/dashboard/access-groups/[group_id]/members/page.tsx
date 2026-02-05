'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface GroupMember {
  id: string;
  user_id: string;
  users?: {
    id: string;
    email: string;
    role: string;
  };
}

interface User {
  id: string;
  email: string;
  role: string;
}

export default function GroupMembersPage() {
  const params = useParams();
  const router = useRouter();
  const { get, post, del } = useAuthFetch();
  const groupId = params.group_id as string;

  const [members, setMembers] = useState<GroupMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [adding, setAdding] = useState(false);

  const fetchMembers = useCallback(async () => {
    try {
      const response = await get(`/access-groups/${groupId}/members`);
      if (response.ok) {
        const data = await response.json();
        setMembers(data);
      }
    } catch (error) {
      console.error('Error fetching members:', error);
    } finally {
      setLoading(false);
    }
  }, [groupId, get]);

  const fetchUsers = useCallback(async () => {
    try {
      const response = await get('/users');
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (error) {
      console.error('Error fetching users:', error);
    }
  }, [get]);

  useEffect(() => {
    fetchMembers();
    fetchUsers();
  }, [fetchMembers, fetchUsers]);

  const handleAddMember = async () => {
    if (!selectedUserId) return;

    setAdding(true);
    try {
      // First, we need to get the twin_id from the group
      const groupResponse = await get(`/access-groups/${groupId}`);

      if (!groupResponse.ok) {
        throw new Error('Failed to fetch group');
      }

      const group = await groupResponse.json();
      const twinId = group.twin_id;

      const response = await post(`/twins/${twinId}/group-memberships`, {
        user_id: selectedUserId,
        group_id: groupId
      });

      if (response.ok) {
        setShowAddModal(false);
        setSelectedUserId('');
        fetchMembers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to add member'}`);
      }
    } catch (error) {
      console.error('Error adding member:', error);
      alert('Failed to add member');
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveMember = async (membershipId: string) => {
    if (!confirm('Are you sure you want to remove this member from the group?')) {
      return;
    }

    try {
      const response = await del(`/group-memberships/${membershipId}`);

      if (response.ok) {
        fetchMembers();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to remove member'}`);
      }
    } catch (error) {
      console.error('Error removing member:', error);
      alert('Failed to remove member');
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <button
            onClick={() => router.back()}
            className="text-blue-600 hover:underline mb-2"
          >
            ← Back to Groups
          </button>
          <h1 className="text-3xl font-bold">Group Members</h1>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Add Member
        </button>
      </div>

      <div className="space-y-4">
        {members.length === 0 ? (
          <p className="text-gray-500">No members in this group yet.</p>
        ) : (
          members.map((member) => (
            <div
              key={member.id}
              className="border border-gray-200 rounded-lg p-4 flex justify-between items-center"
            >
              <div>
                <div className="font-semibold">
                  {member.users?.email || member.user_id}
                </div>
                {member.users?.role && (
                  <div className="text-sm text-gray-500">Role: {member.users.role}</div>
                )}
              </div>
              <button
                onClick={() => handleRemoveMember(member.id)}
                className="px-3 py-1 text-red-600 hover:bg-red-50 rounded"
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-2xl font-bold mb-4">Add Member to Group</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Select User</label>
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">-- Select a user --</option>
                  {users.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.email} ({user.role})
                    </option>
                  ))}
                </select>
                {users.length === 0 && (
                  <p className="text-sm text-gray-500 mt-2">
                    No users available. User management endpoint needed.
                  </p>
                )}
              </div>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                  disabled={adding}
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddMember}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  disabled={adding || !selectedUserId}
                >
                  {adding ? 'Adding...' : 'Add'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
