/**
 * Therapist ↔ Client Portal Bridge Context
 *
 * Picks between three providers based on VITE_USE_MOCK_PROVIDER env var:
 *   undefined / 'true' / '1'  → Mock      (localStorage, no backend)
 *   'dummy'                   → Dummy     (real backend, dev token bypass)
 *   'false' / '0' / 'real'    → Real      (real backend, real Firebase token)
 */

import React, { createContext, useContext, useMemo } from 'react';
import type { TherapistClientBridgeProvider } from '../types/therapistClientBridge';
import { TherapistClientBridgeMockProvider } from '../providers/TherapistClientBridgeMockProvider';
import { TherapistClientBridgeRealProvider } from '../providers/TherapistClientBridgeRealProvider';
import { DummyTherapistClientBridgeProvider } from '../providers/DummyTherapistClientBridgeProvider';

type ProviderMode = 'mock' | 'dummy' | 'real';

function getProviderMode(): ProviderMode {
  const v = (import.meta.env.VITE_USE_MOCK_PROVIDER as string | undefined)?.toLowerCase();
  if (v === undefined) return 'mock';
  if (v === 'true' || v === '1') return 'mock';
  if (v === 'dummy') return 'dummy';
  if (v === 'false' || v === '0' || v === 'real') return 'real';
  return 'mock';  // unknown value → safe default
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const TherapistClientBridgeContext = createContext<TherapistClientBridgeProvider | null>(null);

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTherapistBridge(): TherapistClientBridgeProvider {
  const ctx = useContext(TherapistClientBridgeContext);
  if (!ctx) {
    throw new Error('useTherapistBridge must be used inside <TherapistClientBridgeProviderWrapper>');
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider wrapper
// ---------------------------------------------------------------------------

export function TherapistClientBridgeProviderWrapper({ children }: { children: React.ReactNode }) {
  const provider = useMemo<TherapistClientBridgeProvider>(() => {
    const mode = getProviderMode();
    switch (mode) {
      case 'dummy': return new DummyTherapistClientBridgeProvider();
      case 'real':  return new TherapistClientBridgeRealProvider();
      case 'mock':
      default:      return new TherapistClientBridgeMockProvider();
    }
  }, []);
  return (
    <TherapistClientBridgeContext.Provider value={provider}>
      {children}
    </TherapistClientBridgeContext.Provider>
  );
}

export default TherapistClientBridgeContext;
