/**
 * Patient invitation tracking — mock implementation.
 *
 * Stores invitations in localStorage so the UI feels real without a backend.
 *
 * Phase 6 will replace these calls with backend endpoints that:
 *   1. Create the Firebase user
 *   2. Generate a magic sign-in link
 *   3. Email it to the patient
 *   4. Write a /users/{uid} doc with role=patient + patientId
 *
 * The function signatures here stay identical — Phase 6 only swaps the implementation.
 */

export type InvitationStatus = 'NOT_INVITED' | 'PENDING' | 'ACTIVE' | 'EXPIRED';

export interface PatientInvitation {
  patientId: string;
  email: string;
  invitedAt: string;        // ISO timestamp
  invitedBy: string;         // therapist email
  status: InvitationStatus;
  activatedAt?: string;      // when patient first signed in
  expiresAt?: string;        // ISO timestamp (mocked: 7 days from invite)
}

const STORAGE_KEY = 'patient-invitations-v1';

function loadAll(): Record<string, PatientInvitation> {
  if (typeof window === 'undefined' || !window.localStorage) return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, PatientInvitation>) : {};
  } catch {
    return {};
  }
}

function saveAll(data: Record<string, PatientInvitation>): void {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn('[patientInvitations] Failed to save:', e);
  }
}

/**
 * Send an invitation to a patient.
 * In mock mode: just stores in localStorage. In Phase 6: triggers backend + email.
 */
export async function invitePatient(
  patientId: string,
  email: string,
  invitedBy: string,
): Promise<PatientInvitation> {
  const now = new Date();
  const expires = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);  // 7 days
  const inv: PatientInvitation = {
    patientId,
    email: email.toLowerCase().trim(),
    invitedAt: now.toISOString(),
    invitedBy,
    status: 'PENDING',
    expiresAt: expires.toISOString(),
  };
  const all = loadAll();
  all[patientId] = inv;
  saveAll(all);

  console.log(`[mock] Would email magic sign-in link to ${inv.email}`);
  return inv;
}

/**
 * Get the current invitation state for a patient.
 * Returns null if never invited.
 */
export function getInvitation(patientId: string): PatientInvitation | null {
  const all = loadAll();
  const inv = all[patientId];
  if (!inv) return null;

  // Auto-expire if past expiresAt and still PENDING
  if (inv.status === 'PENDING' && inv.expiresAt && new Date(inv.expiresAt) < new Date()) {
    inv.status = 'EXPIRED';
    all[patientId] = inv;
    saveAll(all);
  }
  return inv;
}

/**
 * Get the simple status (for displaying as a chip).
 */
export function getInvitationStatus(patientId: string): InvitationStatus {
  return getInvitation(patientId)?.status ?? 'NOT_INVITED';
}

/**
 * Resend an invitation (resets the expiry).
 */
export async function resendInvitation(
  patientId: string,
  invitedBy: string,
): Promise<PatientInvitation | null> {
  const existing = getInvitation(patientId);
  if (!existing) return null;
  return invitePatient(patientId, existing.email, invitedBy);
}

/**
 * Mark an invitation as activated (mock only — Phase 6 backend will set this).
 */
export function markActivated(patientId: string): void {
  const all = loadAll();
  if (all[patientId]) {
    all[patientId].status = 'ACTIVE';
    all[patientId].activatedAt = new Date().toISOString();
    saveAll(all);
  }
}

/**
 * Cancel/revoke an invitation.
 */
export function revokeInvitation(patientId: string): void {
  const all = loadAll();
  delete all[patientId];
  saveAll(all);
}
