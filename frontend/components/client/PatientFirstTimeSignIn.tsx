/**
 * PatientFirstTimeSignIn — landing screen when a patient clicks the magic
 * sign-in link in their invitation email.
 *
 * Reads ?patient=... and ?token=... from the URL, validates them, then
 * routes the patient into the portal.
 *
 * In mock mode (now): token is trusted blindly, we just mark the invitation
 * as activated and redirect into the dashboard.
 *
 * In Phase 6: token will be a Firebase email-link sign-in token. We'll call
 * Firebase's signInWithEmailLink(auth, email, currentUrl) which validates the
 * token cryptographically and creates a real session.
 */
import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Stack,
  CircularProgress,
  Alert,
  TextField,
} from '@mui/material';
import { CheckCircle, ErrorOutline, MailOutline } from '@mui/icons-material';
import { getInvitation, markActivated } from '../../utils/patientInvitations';

type Step = 'validating' | 'confirm-email' | 'success' | 'error';

interface Props {
  onContinueToPortal: () => void;
}

export const PatientFirstTimeSignIn: React.FC<Props> = ({ onContinueToPortal }) => {
  const params = new URLSearchParams(window.location.search);
  const patientId = params.get('patient') || '';
  const token = params.get('token') || '';

  const [step, setStep] = useState<Step>('validating');
  const [error, setError] = useState<string | null>(null);
  const [confirmEmail, setConfirmEmail] = useState('');
  const [invitedEmail, setInvitedEmail] = useState<string | null>(null);

  useEffect(() => {
    // Mock validation: a real token is just present; Phase 6 verifies cryptographically.
    setTimeout(() => {
      if (!patientId || !token) {
        setError('This sign-in link is missing required information. Ask your therapist for a new invitation.');
        setStep('error');
        return;
      }
      const inv = getInvitation(patientId);
      if (!inv) {
        setError('No invitation found for this link. It may have been revoked.');
        setStep('error');
        return;
      }
      if (inv.status === 'EXPIRED') {
        setError('This invitation has expired. Ask your therapist to send a fresh one.');
        setStep('error');
        return;
      }
      if (inv.status === 'ACTIVE') {
        // Already activated — Phase 6 would re-validate the session here
        setStep('success');
        return;
      }
      // Pending → ask for email confirmation as a soft verification step
      setInvitedEmail(inv.email);
      setStep('confirm-email');
    }, 600);
  }, [patientId, token]);

  const handleConfirm = () => {
    if (confirmEmail.trim().toLowerCase() !== (invitedEmail || '').toLowerCase()) {
      setError("That email doesn't match what your therapist invited. Please check spelling.");
      return;
    }
    setError(null);
    markActivated(patientId);
    setStep('success');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: 'background.default',
        px: 2,
      }}
    >
      <Card sx={{ maxWidth: 480, width: '100%' }}>
        <CardContent sx={{ p: 4 }}>
          {step === 'validating' && (
            <Stack alignItems="center" spacing={2}>
              <CircularProgress />
              <Typography>Verifying your sign-in link…</Typography>
            </Stack>
          )}

          {step === 'confirm-email' && (
            <Stack spacing={2.5}>
              <Stack direction="row" alignItems="center" spacing={1}>
                <MailOutline color="primary" />
                <Typography variant="h5" component="h1">
                  Welcome
                </Typography>
              </Stack>
              <Typography variant="body1" color="text.secondary">
                You're about to access your TherAssist mental wellness portal. Confirm your email address to continue.
              </Typography>
              <TextField
                label="Your email address"
                type="email"
                value={confirmEmail}
                onChange={(e) => {
                  setConfirmEmail(e.target.value);
                  setError(null);
                }}
                fullWidth
                autoFocus
                placeholder="you@example.com"
              />
              {error && <Alert severity="error">{error}</Alert>}
              <Button
                variant="contained"
                size="large"
                onClick={handleConfirm}
                disabled={!confirmEmail.trim()}
              >
                Continue to my portal
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
                🔒 Your portal is private — only you and your therapist can see what's in it.
              </Typography>
            </Stack>
          )}

          {step === 'success' && (
            <Stack alignItems="center" spacing={2}>
              <CheckCircle sx={{ fontSize: 64, color: 'success.main' }} />
              <Typography variant="h5">You're signed in</Typography>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                Welcome to your TherAssist portal. Take a look around — your therapist has prepared things for you.
              </Typography>
              <Button variant="contained" size="large" onClick={onContinueToPortal} fullWidth>
                Open my portal
              </Button>
            </Stack>
          )}

          {step === 'error' && (
            <Stack alignItems="center" spacing={2}>
              <ErrorOutline sx={{ fontSize: 64, color: 'error.main' }} />
              <Typography variant="h5">Sign-in link issue</Typography>
              <Alert severity="error" sx={{ width: '100%' }}>{error}</Alert>
              <Typography variant="body2" color="text.secondary" textAlign="center">
                Contact your therapist for help getting a fresh invitation.
              </Typography>
            </Stack>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default PatientFirstTimeSignIn;
