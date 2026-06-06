/**
 * PatientInvitationStatus — small chip showing the invitation state for a patient.
 *
 *   NOT_INVITED → no chip rendered (default state)
 *   PENDING     → orange "Invitation pending" chip
 *   ACTIVE      → green "Portal active" chip
 *   EXPIRED     → gray "Invitation expired" chip
 *
 * Used in: Patient detail header, Patients list table (optional).
 */
import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import {
  HourglassEmpty,
  CheckCircleOutline,
  ErrorOutline,
} from '@mui/icons-material';
import { getInvitation, type InvitationStatus } from '../../utils/patientInvitations';

interface Props {
  patientId: string;
  size?: 'small' | 'medium';
}

const STATUS_CONFIG: Record<
  Exclude<InvitationStatus, 'NOT_INVITED'>,
  {
    label: string;
    color: 'warning' | 'success' | 'default';
    icon: React.ReactElement;
    tooltip: (email: string, date: string) => string;
  }
> = {
  PENDING: {
    label: 'Invitation pending',
    color: 'warning',
    icon: <HourglassEmpty fontSize="small" />,
    tooltip: (email, date) => `Invited ${email} on ${date}. Awaiting first sign-in.`,
  },
  ACTIVE: {
    label: 'Portal active',
    color: 'success',
    icon: <CheckCircleOutline fontSize="small" />,
    tooltip: (email, date) => `${email} activated on ${date}.`,
  },
  EXPIRED: {
    label: 'Invitation expired',
    color: 'default',
    icon: <ErrorOutline fontSize="small" />,
    tooltip: (email) => `Invitation to ${email} expired. Resend from "Invite to Portal".`,
  },
};

export const PatientInvitationStatus: React.FC<Props> = ({ patientId, size = 'small' }) => {
  const inv = getInvitation(patientId);
  if (!inv || inv.status === 'NOT_INVITED') return null;

  const config = STATUS_CONFIG[inv.status];
  const displayDate = new Date(inv.activatedAt || inv.invitedAt).toLocaleDateString();

  return (
    <Tooltip title={config.tooltip(inv.email, displayDate)}>
      <Chip
        size={size}
        color={config.color}
        icon={config.icon}
        label={config.label}
        variant="outlined"
      />
    </Tooltip>
  );
};

export default PatientInvitationStatus;
