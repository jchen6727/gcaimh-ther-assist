/**
 * Dummy Provider — Therapist ↔ Client Portal Bridge
 *
 * Acts like the Real provider (calls the backend portal API) but uses a hardcoded
 * dev token instead of a Firebase ID token. Lets us validate the full stack
 * (frontend → backend → Firestore) BEFORE real Firebase Auth is wired (Phase 4).
 *
 * Backend MUST be deployed with PORTAL_DEV_AUTH_BYPASS=true for this to work.
 * NEVER deploy production with that env var set.
 *
 * Token format: 'dev-therapist-<email>' (backend decodes role + email from the token).
 *
 * Configure via env:
 *   VITE_DUMMY_THERAPIST_EMAIL=mohsin.sardar@downstate.edu   (defaults to this)
 */
import { setPortalAuthOverride } from './portalApiClient';
import { TherapistClientBridgeRealProvider } from './TherapistClientBridgeRealProvider';

const DEFAULT_DUMMY_EMAIL = 'mohsin.sardar@downstate.edu';

export class DummyTherapistClientBridgeProvider extends TherapistClientBridgeRealProvider {
  constructor() {
    super();
    const email = (import.meta.env.VITE_DUMMY_THERAPIST_EMAIL as string | undefined) || DEFAULT_DUMMY_EMAIL;
    setPortalAuthOverride(`dev-therapist-${email}`);
    if (typeof console !== 'undefined') {
      console.warn(
        `[DummyTherapistProvider] Using dev token for ${email}. ` +
        `Backend must have PORTAL_DEV_AUTH_BYPASS=true.`,
      );
    }
  }
}
