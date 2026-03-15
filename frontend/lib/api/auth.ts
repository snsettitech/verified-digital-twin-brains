/**
 * Auth API Client
 * Connected accounts (LinkedIn, etc.) for onboarding and profile.
 */

import { authFetchStandalone } from '@/lib/hooks/useAuthFetch';
import { resolveApiBaseUrl } from '@/lib/api';
import { API_ENDPOINTS } from '@/lib/constants';

const BASE_URL = resolveApiBaseUrl();

export interface ConnectedAccount {
  id: string;
  user_id: string;
  provider: string;
  provider_user_id?: string;
  profile_snapshot?: {
    profile_url?: string;
    display_name?: string;
    image_url?: string;
    headline?: string;
  };
  created_at: string;
  updated_at: string;
}

export interface ConnectedAccountsResponse {
  accounts: ConnectedAccount[];
}

export async function getConnectedAccounts(): Promise<ConnectedAccountsResponse> {
  const url = `${BASE_URL}${API_ENDPOINTS.AUTH_CONNECTED_ACCOUNTS}`;
  const response = await authFetchStandalone(url);
  if (!response.ok) {
    return { accounts: [] };
  }
  return response.json();
}
