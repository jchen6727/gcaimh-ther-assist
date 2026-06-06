/**
 * Dummy Provider — Patient Client Portal
 *
 * Like createRealClientPortalProvider but uses a hardcoded dev token.
 * Backend MUST have PORTAL_DEV_AUTH_BYPASS=true.
 *
 * Token: 'dev-patient-<email>'
 * Configure via env:
 *   VITE_DUMMY_PATIENT_EMAIL=jane.doe@example.com   (defaults to this)
 */
import { setPortalAuthOverride } from './portalApiClient';
import { createRealClientPortalProvider } from './ClientPortalRealProvider';

const DEFAULT_DUMMY_EMAIL = 'jane.doe@example.com';

export function createDummyClientPortalProvider() {
  const email = (import.meta.env.VITE_DUMMY_PATIENT_EMAIL as string | undefined) || DEFAULT_DUMMY_EMAIL;
  setPortalAuthOverride(`dev-patient-${email}`);
  if (typeof console !== 'undefined') {
    console.warn(
      `[DummyClientPortalProvider] Using dev token for ${email}. ` +
      `Backend must have PORTAL_DEV_AUTH_BYPASS=true.`,
    );
  }
  return createRealClientPortalProvider();
}
