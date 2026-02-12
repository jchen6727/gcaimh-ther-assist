// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import React, { useState, useEffect, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Divider,
  Chip,
  CircularProgress,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Paper,
  IconButton,
} from '@mui/material';
import {
  Close,
  Assignment,
  TrendingUp,
  Warning,
  CheckCircle,
  Psychology,
  MenuBook,
  Download,
  Print,
  Info,
  RadioButtonUnchecked,
} from '@mui/icons-material';
import { SessionSummary } from '../types/types';
import { formatTimestamp } from '../utils/timeUtils';

// Loading step definitions for the progress UI
const LOADING_STEPS = [
  { label: 'Analyzing session transcript...', threshold: 0 },
  { label: 'Identifying key therapeutic moments...', threshold: 5 },
  { label: 'Evaluating treatment effectiveness...', threshold: 15 },
  { label: 'Generating clinical recommendations...', threshold: 25 },
  { label: 'Compiling homework assignments...', threshold: 40 },
];
const ESTIMATED_TOTAL_SECONDS = 45;

interface SessionSummaryModalProps {
  open: boolean;
  onClose: () => void;
  summary: SessionSummary | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  sessionId: string | null;
}

const SessionSummaryModal: React.FC<SessionSummaryModalProps> = ({
  open,
  onClose,
  summary,
  loading,
  error,
  onRetry,
  sessionId,
}) => {
  // Loading progress state
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Start/stop elapsed timer based on loading state
  useEffect(() => {
    if (loading) {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [loading]);

  // Determine current loading step index based on elapsed time
  const currentStepIndex = LOADING_STEPS.reduce((acc, step, idx) => {
    return elapsedSeconds >= step.threshold ? idx : acc;
  }, 0);

  // Progress percentage (capped at 95% until actually complete)
  const progressPercent = Math.min((elapsedSeconds / ESTIMATED_TOTAL_SECONDS) * 100, 95);

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low':
        return '#10b981';
      case 'moderate':
        return '#f59e0b';
      case 'high':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const handleExport = () => {
    if (!summary) return;

    const content = JSON.stringify(summary, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session-summary-${sessionId || 'unknown'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    window.print();
  };

  // Defensive defaults — prevents crash when backend returns incomplete summary
  const safe = summary ? {
    techniques_used: [] as string[],
    key_moments: [] as Array<{ time: string; description: string; significance: string }>,
    progress_indicators: [] as string[],
    areas_for_improvement: [] as string[],
    homework_assignments: [] as Array<{ task: string; rationale: string; manual_reference?: string }>,
    follow_up_recommendations: [] as string[],
    risk_assessment: { level: 'low', factors: [] as string[] },
    duration_minutes: 0,
    session_date: new Date().toISOString(),
    ...summary, // real values override defaults
  } : null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: '24px',
          minHeight: '80vh',
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.75) 0%, rgba(248, 250, 252, 0.85) 100%)',
          backdropFilter: 'blur(40px) saturate(200%)',
          WebkitBackdropFilter: 'blur(40px) saturate(200%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 25px 70px -10px rgba(0, 0, 0, 0.18)',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            borderRadius: '24px',
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.35) 0%, transparent 100%)',
            pointerEvents: 'none',
          },
        },
      }}
    >
      <DialogTitle sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'linear-gradient(135deg, rgba(11, 87, 208, 0.9) 0%, rgba(0, 99, 155, 0.9) 100%)',
        color: 'white',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Assignment sx={{ fontSize: 28 }} />
          <Typography variant="h5" fontWeight={600} sx={{ fontSize: '1.75rem' }}>
            Session Summary
          </Typography>
          {sessionId && (
            <Chip
              label={`Session ${sessionId}`}
              sx={{
                background: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.3)',
              }}
            />
          )}
        </Box>
        <IconButton
          onClick={onClose}
          sx={{ color: 'white' }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 3 }}>
        {loading ? (
          /* ── Enhanced Loading Progress UI ── */
          <Box sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 400,
            flexDirection: 'column',
            gap: 3,
            py: 4,
          }}>
            {/* Header */}
            <Box sx={{ textAlign: 'center', mb: 1 }}>
              <Psychology sx={{ fontSize: 56, color: '#0b57d0', mb: 1 }} />
              <Typography variant="h6" fontWeight={600} sx={{ color: '#1a1a2e', fontSize: '1.3rem' }}>
                AI Clinical Analysis in Progress
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontSize: '0.95rem' }}>
                The AI model is reviewing your session with clinical evidence
              </Typography>
            </Box>

            {/* Progress Bar */}
            <Box sx={{ width: '100%', maxWidth: 480, px: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>
                  Progress
                </Typography>
                <Typography variant="caption" fontWeight={600} sx={{ color: '#0b57d0', fontSize: '0.85rem' }}>
                  Elapsed: {elapsedSeconds}s
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={progressPercent}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  backgroundColor: 'rgba(11, 87, 208, 0.1)',
                  '& .MuiLinearProgress-bar': {
                    borderRadius: 4,
                    background: 'linear-gradient(90deg, #0b57d0 0%, #1a73e8 100%)',
                  },
                }}
              />
            </Box>

            {/* Step Indicators */}
            <Box sx={{ width: '100%', maxWidth: 480, px: 2 }}>
              {LOADING_STEPS.map((step, idx) => {
                const isComplete = idx < currentStepIndex;
                const isCurrent = idx === currentStepIndex;
                const isPending = idx > currentStepIndex;

                return (
                  <Box
                    key={idx}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1.5,
                      py: 0.8,
                      opacity: isPending ? 0.4 : 1,
                      transition: 'opacity 0.3s ease',
                    }}
                  >
                    {isComplete ? (
                      <CheckCircle sx={{ fontSize: 22, color: '#10b981' }} />
                    ) : isCurrent ? (
                      <CircularProgress size={20} thickness={5} sx={{ color: '#0b57d0' }} />
                    ) : (
                      <RadioButtonUnchecked sx={{ fontSize: 22, color: '#ccc' }} />
                    )}
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: isCurrent ? 600 : 400,
                        color: isCurrent ? '#0b57d0' : isComplete ? '#10b981' : '#999',
                        fontSize: '0.95rem',
                      }}
                    >
                      {step.label}
                    </Typography>
                  </Box>
                );
              })}
            </Box>

            {/* Helpful tip */}
            <Typography
              variant="caption"
              sx={{
                color: '#888',
                textAlign: 'center',
                maxWidth: 400,
                mt: 1,
                fontSize: '0.85rem',
                fontStyle: 'italic',
              }}
            >
              Analysis typically completes in 30–45 seconds. Please do not close this window.
            </Typography>
          </Box>
        ) : safe ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Session Overview */}
            <Paper sx={{
              p: 3,
              background: 'linear-gradient(135deg, rgba(250, 251, 253, 0.6) 0%, rgba(245, 247, 250, 0.7) 100%)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              border: '1px solid rgba(255, 255, 255, 0.4)',
              boxShadow: '0 8px 20px -4px rgba(0, 0, 0, 0.08)',
            }}>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.35rem' }}>
                <TrendingUp /> Session Overview
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 2, mt: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Duration</Typography>
                  <Typography variant="body1" fontWeight={600} sx={{ fontSize: '1.1rem' }}>
                    {safe.duration_minutes} minutes
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Techniques Used</Typography>
                  <Typography variant="body1" fontWeight={600} sx={{ fontSize: '1.1rem' }}>
                    {safe.techniques_used.length} techniques
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Patient Risk Level</Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Chip
                      label={safe.risk_assessment.level.toUpperCase()}
                      size="small"
                      sx={{
                        bgcolor: getRiskColor(safe.risk_assessment.level),
                        color: 'white',
                        fontWeight: 600,
                        fontSize: '0.8rem',
                      }}
                    />
                  </Box>
                </Box>
              </Box>
            </Paper>

            {/* Key Moments */}
            {safe.key_moments.length > 0 && (
              <Box>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.35rem' }}>
                  <Psychology /> Key Therapeutic Moments
                </Typography>
                <List>
                  {safe.key_moments.map((moment, idx) => (
                    <ListItem key={idx} sx={{ pl: 0 }}>
                      <ListItemIcon>
                        <CheckCircle color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ fontSize: '1.05rem' }}>
                            <Chip label={formatTimestamp(moment.time)} size="small" sx={{ mr: 1, fontSize: '0.8rem' }} />
                            <span style={{ fontSize: '1.05rem' }}>{moment.description}</span>
                          </Box>
                        }
                        secondary={<span style={{ fontSize: '0.95rem' }}>{moment.significance}</span>}
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}

            <Divider />

            {/* Progress & Areas for Improvement */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 3 }}>
              <Box>
                <Typography variant="h6" gutterBottom sx={{ fontSize: '1.35rem' }}>
                  Progress Indicators
                </Typography>
                {safe.progress_indicators.length > 0 ? (
                  <List dense>
                    {safe.progress_indicators.map((indicator, idx) => (
                      <ListItem key={idx} sx={{ pl: 0 }}>
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          <CheckCircle fontSize="small" color="success" />
                        </ListItemIcon>
                        <ListItemText primary={<span style={{ fontSize: '1.05rem' }}>{indicator}</span>} />
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                    No progress indicators available for this session.
                  </Typography>
                )}
              </Box>

              <Box>
                <Typography variant="h6" gutterBottom sx={{ fontSize: '1.35rem' }}>
                  Areas for Improvement
                </Typography>
                {safe.areas_for_improvement.length > 0 ? (
                  <List dense>
                    {safe.areas_for_improvement.map((area, idx) => (
                      <ListItem key={idx} sx={{ pl: 0 }}>
                        <ListItemIcon sx={{ minWidth: 32 }}>
                          <Warning fontSize="small" color="warning" />
                        </ListItemIcon>
                        <ListItemText primary={<span style={{ fontSize: '1.05rem' }}>{area}</span>} />
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                    No specific areas for improvement identified.
                  </Typography>
                )}
              </Box>
            </Box>

            <Divider />

            {/* Homework Assignments */}
            {safe.homework_assignments.length > 0 && (
              <Box>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.35rem' }}>
                  <Assignment /> Homework Assignments
                </Typography>
                {safe.homework_assignments.map((hw, idx) => (
                  <Paper key={idx} sx={{
                    p: 2,
                    mb: 2,
                    background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(16, 185, 129, 0.04) 100%)',
                    backdropFilter: 'blur(8px)',
                    WebkitBackdropFilter: 'blur(8px)',
                    border: '1px solid rgba(16, 185, 129, 0.2)',
                  }}>
                    <Typography variant="body1" fontWeight={600} gutterBottom sx={{ fontSize: '1.1rem' }}>
                      {hw.task}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom sx={{ fontSize: '1rem' }}>
                      Rationale: {hw.rationale}
                    </Typography>
                    {hw.manual_reference && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 1 }}>
                        <MenuBook fontSize="small" color="action" />
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.9rem' }}>
                          {hw.manual_reference}
                        </Typography>
                      </Box>
                    )}
                  </Paper>
                ))}
              </Box>
            )}

            {/* Follow-up Recommendations */}
            {safe.follow_up_recommendations.length > 0 && (
              <Box>
                <Typography variant="h6" gutterBottom sx={{ fontSize: '1.35rem' }}>
                  Follow-up Recommendations
                </Typography>
                <List dense>
                  {safe.follow_up_recommendations.map((rec, idx) => (
                    <ListItem key={idx} sx={{ pl: 0 }}>
                      <ListItemIcon sx={{ minWidth: 32 }}>
                        <Info fontSize="small" color="info" />
                      </ListItemIcon>
                      <ListItemText primary={<span style={{ fontSize: '1.05rem' }}>{rec}</span>} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            )}
          </Box>
        ) : error ? (
          <Box sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 400,
            flexDirection: 'column',
            gap: 2,
          }}>
            <Warning color="error" sx={{ fontSize: 48 }} />
            <Typography color="error">{error}</Typography>
            <Button variant="contained" onClick={onRetry}>
              Retry
            </Button>
          </Box>
        ) : null}
      </DialogContent>

      <DialogActions sx={{ p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
        <Button
          startIcon={<Download />}
          onClick={handleExport}
          disabled={!summary}
        >
          Export
        </Button>
        <Button
          startIcon={<Print />}
          onClick={handlePrint}
          disabled={!summary}
        >
          Print
        </Button>
        <Button onClick={onClose} variant="contained">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SessionSummaryModal;
