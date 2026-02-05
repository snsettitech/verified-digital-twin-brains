'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthFetch } from '@/lib/hooks/useAuthFetch';

interface GroupLimit {
  id: string;
  limit_type: string;
  limit_value: number;
}

interface GroupOverride {
  id: string;
  override_type: string;
  override_value: any;
}

export default function GroupSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const { get, post } = useAuthFetch();
  const groupId = params.group_id as string;

  const [group, setGroup] = useState<any>(null);
  const [limits, setLimits] = useState<GroupLimit[]>([]);
  const [overrides, setOverrides] = useState<GroupOverride[]>([]);
  const [loading, setLoading] = useState(true);

  // Form states
  const [systemPrompt, setSystemPrompt] = useState('');
  const [temperature, setTemperature] = useState(0);
  const [maxTokens, setMaxTokens] = useState<number | null>(null);
  const [requestsPerHour, setRequestsPerHour] = useState<number | null>(null);
  const [requestsPerDay, setRequestsPerDay] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchGroupData = useCallback(async () => {
    try {
      const response = await get(`/access-groups/${groupId}`);
      if (response.ok) {
        const data = await response.json();
        setGroup(data);
      }
    } catch (error) {
      console.error('Error fetching group:', error);
    } finally {
      setLoading(false);
    }
  }, [groupId, get]);

  const fetchLimits = useCallback(async () => {
    try {
      const response = await get(`/access-groups/${groupId}/limits`);
      if (response.ok) {
        const data = await response.json();
        setLimits(data);

        // Populate form fields
        const rph = data.find((l: GroupLimit) => l.limit_type === 'requests_per_hour');
        const rpd = data.find((l: GroupLimit) => l.limit_type === 'requests_per_day');
        if (rph) setRequestsPerHour(rph.limit_value);
        if (rpd) setRequestsPerDay(rpd.limit_value);
      }
    } catch (error) {
      console.error('Error fetching limits:', error);
    }
  }, [groupId, get]);

  const fetchOverrides = useCallback(async () => {
    try {
      const response = await get(`/access-groups/${groupId}/overrides`);
      if (response.ok) {
        const data = await response.json();
        setOverrides(data);

        // Populate form fields
        const sysPrompt = data.find((o: GroupOverride) => o.override_type === 'system_prompt');
        const temp = data.find((o: GroupOverride) => o.override_type === 'temperature');
        const maxTok = data.find((o: GroupOverride) => o.override_type === 'max_tokens');

        if (sysPrompt) setSystemPrompt(sysPrompt.override_value);
        if (temp) setTemperature(temp.override_value);
        if (maxTok) setMaxTokens(maxTok.override_value);
      }
    } catch (error) {
      console.error('Error fetching overrides:', error);
    }
  }, [groupId, get]);

  useEffect(() => {
    fetchGroupData();
    fetchLimits();
    fetchOverrides();
  }, [fetchGroupData, fetchLimits, fetchOverrides]);

  const handleSaveLimit = async (limitType: string, limitValue: number | null) => {
    if (limitValue === null || limitValue <= 0) {
      alert('Please enter a valid limit value');
      return;
    }

    setSaving(true);
    try {
      const response = await post(`/access-groups/${groupId}/limits?limit_type=${encodeURIComponent(limitType)}&limit_value=${limitValue}`, {});

      if (response.ok) {
        fetchLimits();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to save limit'}`);
      }
    } catch (error) {
      console.error('Error saving limit:', error);
      alert('Failed to save limit');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveOverride = async (overrideType: string, overrideValue: any) => {
    setSaving(true);
    try {
      const response = await post(`/access-groups/${groupId}/overrides`, {
        override_type: overrideType,
        override_value: overrideValue
      });

      if (response.ok) {
        fetchOverrides();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to save override'}`);
      }
    } catch (error) {
      console.error('Error saving override:', error);
      alert('Failed to save override');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <button
          onClick={() => router.back()}
          className="text-blue-600 hover:underline mb-2"
        >
          ← Back to Groups
        </button>
        <h1 className="text-3xl font-bold">Group Settings & Limits</h1>
        {group && <p className="text-gray-600 mt-2">Group: {group.name}</p>}
      </div>

      <div className="space-y-8">
        {/* System Prompt Override */}
        <div className="border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">System Prompt Override</h2>
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            rows={6}
            placeholder="Enter custom system prompt for this group..."
          />
          <button
            onClick={() => handleSaveOverride('system_prompt', systemPrompt)}
            className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save System Prompt'}
          </button>
        </div>

        {/* Model Parameters */}
        <div className="border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Model Parameters</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">
                Temperature: {temperature}
              </label>
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full"
              />
              <button
                onClick={() => handleSaveOverride('temperature', temperature)}
                className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={saving}
              >
                Save Temperature
              </button>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Max Tokens</label>
              <input
                type="number"
                value={maxTokens || ''}
                onChange={(e) => setMaxTokens(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="Leave empty for default"
              />
              <button
                onClick={() => handleSaveOverride('max_tokens', maxTokens)}
                className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={saving}
              >
                Save Max Tokens
              </button>
            </div>
          </div>
        </div>

        {/* Rate Limits */}
        <div className="border border-gray-200 rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Rate Limits</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Requests per Hour</label>
              <input
                type="number"
                value={requestsPerHour || ''}
                onChange={(e) => setRequestsPerHour(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="Leave empty for no limit"
              />
              <button
                onClick={() => handleSaveLimit('requests_per_hour', requestsPerHour)}
                className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={saving}
              >
                Save Limit
              </button>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Requests per Day</label>
              <input
                type="number"
                value={requestsPerDay || ''}
                onChange={(e) => setRequestsPerDay(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="Leave empty for no limit"
              />
              <button
                onClick={() => handleSaveLimit('requests_per_day', requestsPerDay)}
                className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                disabled={saving}
              >
                Save Limit
              </button>
            </div>
          </div>
        </div>

        {/* Current Limits Display */}
        {limits.length > 0 && (
          <div className="border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Active Limits</h2>
            <div className="space-y-2">
              {limits.map((limit) => (
                <div key={limit.id} className="flex justify-between items-center">
                  <span className="font-medium">{limit.limit_type.replace(/_/g, ' ')}</span>
                  <span>{limit.limit_value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
