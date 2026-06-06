/**
 * InvitePatientDialog — therapist sends a portal invitation to a patient.
 *
 * Three states:
 *   1. 'form'    — enter email, see preview
 *   2. 'sending' — submit in progress (mock: 800ms delay)
 *   3. 'sent'    — confirmation with copy-link option
 *
 * The "magic link" displayed is a mock — Phase 6 wires this to a real Firebase
 * sign-in link sent via email. The UI shape stays the same.
 */
import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  Alert,
  CircularProgress,
  Stack,
  Chip,
  IconButton,
  Divider,
} from '@mui/material';
import {
  MailOutline,
  ContentCopy,
  CheckCircleOutline,
  Refresh,
} from '@mui/icons-material';
import { useAuth } from '../../contexts/AuthContext';
import {
  invitePatient,
  getInvitation,
  resendInvitation,
  type PatientInvitation,
} from '../../utils/patientInvitations';

interface InvitePatientDialogProps {
  open: boolean;
  onClose: () => void;
  patientId: string;
  patientName: string;
  defaultEmail?: string;
  onInvited?: (invitation: PatientInvitation) => void;
}

type DialogStep = 'form' | 'sending' | 'sent';

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export const InvitePatientDialog: React.FC<InvitePatientDialogProps> = ({
  open,
  onClose,
  patientId,
  patientName,
  defaultEmail = '',
  onInvited,
}) => {
  const { currentUser } = useAuth();
  const therapistEmail = currentUser?.email || 'developer@localhost.test';
  const existing = getInvitation(patientId);
  const isResend = !!existing;

  const [step, setStep] = useState<DialogStep>('form');
  const [email, setEmail] = useState(existing?.email || defaultEmail);
  const [error, setError] = useState<string | null>(null);
  const [invitation, setInvitation] = useState<PatientInvitation | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);

  // Reset state when reopened
  useEffect(() => {
    if (open) {
      const current = getInvitation(patientId);
      setEmail(current?.email || defaultEmail);
      setStep('form');
      setError(null);
      setInvitation(null);
      setLinkCopied(false);
    }
  }, [open, patientId, defaultEmail]);

  const handleSend = async () => {
    setError(null);
    const trimmed = email.trim();
    if (!isValidEmail(trimmed)) {
      setError('Please enter a valid email address.');
      return;
    }
    setStep('sending');
    try {
      // Mock delay so the UI shows a real-feeling progress state
      await new Promise(r => setTimeout(r, 800));
      const inv = isResend
        ? await resendInvitation(patientId, therapistEmail)
        : await invitePatient(patientId, trimmed, therapistEmail);
      if (!inv) throw new Error('Failed to create invitation');
      setInvitation(inv);
      setStep('sent');
      onInvited?.(inv);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send invitation');
      setStep('form');
    }
  };

  // Mock magic link — Phase 6 will use Firebase generateSignInLinkForEmail()
  const mockMagicLink = invitation
    ? `${window.location.origin}/patient-signin?patient=${encodeURIComponent(patientId)}&token=mock-${invitation.invitedAt.slice(0, 10)}`
    : '';

  const handleCopyLink = () => {
    if (mockMagicLink) {
      navigator.clipboard.writeText(mockMagicLink);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    }
  };

  return (
    <Dialog open={open} onClose={step === 'sending' ? undefined : onClose} maxWidth="sm" fullWidth>
      {step === 'form' && (
        <>
          <DialogTitle component="div">
            <Stack direction="row" alignItems="center" spacing={1}>
              <MailOutline color="primary" />
              <Typography variant="h6" component="div">
                {isResend ? 'Resend Portal Invitation' : 'Invite to Portal'}
              </Typography>
            </Stack>
            <Typography variant="caption" component="div" color="text.secondary">
              {patientName}
            </Typography>
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                {isResend
                  ? `${patientName} was previously invited on ${new Date(existing!.invitedAt).toLocaleDateString()}. Resending will create a new magic sign-in link and reset the 7-day expiry.`
                  : `${patientName} will receive an email with a secure sign-in link. The link expires in 7 days.`}
              </Typography>
              <TextField
                label="Patient email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                fullWidth
                autoFocus
                error={!!error && error.toLowerCase().includes('email')}
                helperText={error?.toLowerCase().includes('email') ? error : ' '}
                placeholder="patient@example.com"
              />
              {error && !error.toLowerCase().includes('email') && (
                <Alert severity="error">{error}</Alert>
              )}
              <Box sx={{ bgcolor: 'grey.50', p: 2, borderRadius: 1, border: '1px solid', borderColor: 'grey.200' }}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
                  EMAIL PREVIEW
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  Subject: Your TherAssist client portal is ready
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
                  Hi {patientName.split(' ')[0]},
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary' }}>
                  Your therapist {therapistEmail.split('@')[0]} has invited you to your personal mental wellness portal — a space to access your homework, journal, and track your progress between sessions.
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary', fontStyle: 'italic' }}>
                  [Sign in with a single click — no password needed]
                </Typography>
              </Box>
              <Alert severity="info" sx={{ mt: 1 }} icon={false}>
                <Typography variant="caption">
                  🔒 Mock mode: no email is actually sent. Phase 6 will wire this to Firebase Auth + Gmail SMTP.
                </Typography>
              </Alert>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleSend}
              disabled={!email.trim() || !isValidEmail(email)}
              startIcon={isResend ? <Refresh /> : <MailOutline />}
            >
              {isResend ? 'Resend Invitation' : 'Send Invitation'}
            </Button>
          </DialogActions>
        </>
      )}

      {step === 'sending' && (
        <>
          <DialogContent>
            <Stack alignItems="center" spacing={2} sx={{ py: 6 }}>
              <CircularProgress />
              <Typography variant="body1">Sending invitation…</Typography>
            </Stack>
          </DialogContent>
        </>
      )}

      {step === 'sent' && invitation && (
        <>
          <DialogTitle component="div">
            <Stack direction="row" alignItems="center" spacing={1}>
              <CheckCircleOutline sx={{ color: 'success.main' }} />
              <Typography variant="h6" component="div">Invitation Sent</Typography>
            </Stack>
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={2}>
              <Alert severity="success">
                An email with a secure sign-in link has been sent to <strong>{invitation.email}</strong>.
              </Alert>
              <Stack direction="row" spacing={2}>
                <Box flex={1}>
                  <Typography variant="caption" color="text.secondary">EXPIRES</Typography>
                  <Typography variant="body2">
                    {invitation.expiresAt ? new Date(invitation.expiresAt).toLocaleDateString() : '—'}
                  </Typography>
                </Box>
                <Box flex={1}>
                  <Typography variant="caption" color="text.secondary">STATUS</Typography>
                  <Box mt={0.5}>
                    <Chip label="Pending" color="warning" size="small" />
                  </Box>
                </Box>
              </Stack>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  MOCK MAGIC LINK (Phase 6 will email this — for now you can copy it to test the patient flow)
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography
                    variant="caption"
                    sx={{
                      flex: 1,
                      fontFamily: 'monospace',
                      bgcolor: 'grey.100',
                      p: 1,
                      borderRadius: 0.5,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {mockMagicLink}
                  </Typography>
                  <IconButton onClick={handleCopyLink} size="small" title="Copy link">
                    {linkCopied ? <CheckCircleOutline color="success" /> : <ContentCopy />}
                  </IconButton>
                </Stack>
              </Box>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button variant="contained" onClick={onClose}>Done</Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
};

export default InvitePatientDialog;
