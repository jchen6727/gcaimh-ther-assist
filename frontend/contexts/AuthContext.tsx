import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  Auth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup,
  updateProfile,
} from 'firebase/auth';
import { auth as firebaseAuth } from '../firebase-config';

// Cast to Auth type — safe because USE_MOCK_AUTH guards prevent Firebase calls when auth is null
const auth = firebaseAuth as unknown as Auth;

// Check if we should use mock auth (for local development without Firebase)
const USE_MOCK_AUTH = import.meta.env.VITE_USE_MOCK_AUTH === 'true' ||
  !import.meta.env.VITE_FIREBASE_API_KEY ||
  import.meta.env.VITE_FIREBASE_API_KEY === 'placeholder-api-key';

// Mock user object that mimics Firebase User interface
const createMockUser = (): Partial<User> & { getIdToken: () => Promise<string> } => ({
  uid: 'mock-user-uid-12345',
  email: 'developer@localhost.test',
  displayName: 'Local Developer',
  emailVerified: true,
  isAnonymous: false,
  photoURL: null,
  providerData: [],
  refreshToken: 'mock-refresh-token',
  tenantId: null,
  metadata: {
    creationTime: new Date().toISOString(),
    lastSignInTime: new Date().toISOString(),
  } as any,
  getIdToken: async () => 'mock-id-token-for-local-development',
  getIdTokenResult: async () => ({
    token: 'mock-id-token-for-local-development',
    claims: {},
    expirationTime: new Date(Date.now() + 3600000).toISOString(),
    issuedAtTime: new Date().toISOString(),
    signInProvider: 'mock',
    authTime: new Date().toISOString(),
    signInSecondFactor: null,
  }),
  reload: async () => {},
  toJSON: () => ({}),
  delete: async () => {},
});

interface AuthContextType {
  currentUser: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<any>;
  signup: (email: string, password: string, displayName?: string) => Promise<any>;
  logout: () => Promise<void>;
  signInWithGoogle: () => Promise<any>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Helper function to check if email is authorized
  const isEmailAuthorized = (email: string | null): boolean => {
    if (!email) return false;

    const allowedEmails = [
      'anitza@albany.edu',
      'jfboswell197@gmail.com',
      'Salvador.Dura-Bernal@downstate.edu',
      'boswell@albany.edu',
      'developer@localhost.test', // Mock user email
    ];

    return email.endsWith('@google.com') || allowedEmails.includes(email);
  };

  const signup = async (email: string, password: string, displayName?: string) => {
    if (USE_MOCK_AUTH) {
      console.log('[MockAuth] Signup called (mock mode) - auto-returning mock user');
      return { user: createMockUser() };
    }
    const result = await createUserWithEmailAndPassword(auth, email, password);
    if (displayName && result.user) {
      await updateProfile(result.user, { displayName });
    }
    return result;
  };

  const login = (email: string, password: string) => {
    if (USE_MOCK_AUTH) {
      console.log('[MockAuth] Login called (mock mode) - auto-returning mock user');
      return Promise.resolve({ user: createMockUser() });
    }
    return signInWithEmailAndPassword(auth, email, password);
  };

  const logout = async () => {
    if (USE_MOCK_AUTH) {
      console.log('[MockAuth] Logout called (mock mode) - no-op');
      return;
    }
    return signOut(auth);
  };

  const signInWithGoogle = async () => {
    if (USE_MOCK_AUTH) {
      console.log('[MockAuth] Google sign-in called (mock mode) - auto-returning mock user');
      return { user: createMockUser() };
    }
    const provider = new GoogleAuthProvider();
    const result = await signInWithPopup(auth, provider);

    // Check if the email is authorized
    const email = result.user?.email;
    if (!isEmailAuthorized(email)) {
      // Sign out the user if they don't have an authorized email
      await signOut(auth);
      throw new Error('Access restricted to @google.com email addresses and authorized users only.');
    }

    return result;
  };

  useEffect(() => {
    // In mock auth mode, immediately set mock user and skip Firebase auth listener
    if (USE_MOCK_AUTH) {
      console.log('[MockAuth] Mock auth mode enabled - auto-logging in as mock user');
      setCurrentUser(createMockUser() as User);
      setLoading(false);
      return;
    }

    // Real Firebase auth listener
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        // Check if the current user has an authorized email
        const email = user.email;
        if (!isEmailAuthorized(email)) {
          // Sign out the user if they don't have an authorized email
          await signOut(auth);
          setCurrentUser(null);
          setLoading(false);
          return;
        }
      }

      setCurrentUser(user);
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  const value: AuthContextType = {
    currentUser,
    loading,
    login,
    signup,
    logout,
    signInWithGoogle,
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
};
