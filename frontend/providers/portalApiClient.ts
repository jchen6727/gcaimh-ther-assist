/**
 * Shared HTTP client for portal endpoints.
 *
 * Used by TherapistClientBridgeRealProvider and ClientPortalRealProvider to call
 * the backend portal API (storage-access-function /portal/*).
 *
 * Handles:
 *  - Firebase ID token attachment (fresh per request — Firebase auto-refreshes)
 *  - Base URL resolution from VITE_STORAGE_ACCESS_URL
 *  - Standard error mapping (400/401/403/404/409/500 → typed Error)
 *  - JSON encoding/decoding
 *  - Query param building for pagination
 */
import { auth } from '../firebase-config';
import type { Auth } from 'firebase/auth';

// VITE_STORAGE_ACCESS_URL points at storage_access endpoint (e.g. /api/storage/storage_access in sidecar mode).
// Portal endpoints are at /portal/* on the same Cloud Run service, so strip the /storage_access suffix.
function getBaseUrl(): string {
  const raw = (import.meta.env.VITE_STORAGE_ACCESS_URL as string) || '';
  // Common forms:
  //   /api/storage/storage_access       -> /api/storage
  //   https://x.run.app/storage_access  -> https://x.run.app
  //   /storage_access                    -> ''
  return raw.replace(/\/storage_access\/?$/, '');
}

export class PortalApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
    this.name = 'PortalApiError';
  }
}

async function getIdToken(): Promise<string | null> {
  if (!auth) return null;  // Mock auth mode — no real token
  try {
    const user = (auth as unknown as Auth).currentUser;
    if (!user) return null;
    return await user.getIdToken();
  } catch (e) {
    console.error('[portalApiClient] Failed to get ID token', e);
    return null;
  }
}

/**
 * Per-call token override.
 * If set (e.g., by DummyProvider), this is used as the Bearer token instead of
 * trying to read from Firebase. Set globally for the lifetime of the provider.
 */
let _tokenOverride: string | null = null;

export function setPortalAuthOverride(token: string | null): void {
  _tokenOverride = token;
}

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
  query?: Record<string, string | number | undefined>,
): Promise<T> {
  const token = _tokenOverride ?? (await getIdToken());
  if (!token) {
    throw new PortalApiError(401, 'Not authenticated — no Firebase ID token available');
  }

  let url = `${getBaseUrl()}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') {
        params.append(k, String(v));
      }
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const init: RequestInit = {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const res = await fetch(url, init);

  if (!res.ok) {
    let errorBody: unknown = undefined;
    let message = `Portal API ${res.status} ${res.statusText}`;
    try {
      errorBody = await res.json();
      if (errorBody && typeof errorBody === 'object' && 'error' in errorBody) {
        message = String((errorBody as { error: unknown }).error);
      }
    } catch {
      // not JSON, leave as-is
    }
    throw new PortalApiError(res.status, message, errorBody);
  }

  // Handle empty body (204, or some PATCH/POSTs that return null)
  const text = await res.text();
  if (!text) return undefined as unknown as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined as unknown as T;
  }
}

export const portalApi = {
  get: <T = unknown>(path: string, query?: Record<string, string | number | undefined>) =>
    request<T>('GET', path, undefined, query),
  post: <T = unknown>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T = unknown>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  del: <T = unknown>(path: string) => request<T>('DELETE', path),
};
