/**
 * TrendsPanel — symptoms comparison + change-over-time view.
 *
 * Three sections:
 *   1. Overlaid line chart: all measures normalized to 0..1 on one chart so the
 *      therapist sees relative trajectories at a glance.
 *   2. Delta cards: latest score, change vs first reading, change vs last reading.
 *   3. Severity transitions log: every time a measure crossed a severity bucket.
 *
 * Uses overview.trend (already provided by getClientPortalOverview).
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Box, Card, CardContent, Stack, Typography, Chip,
  Alert, Skeleton, Tooltip,
  Table, TableHead, TableBody, TableRow, TableCell,
} from '@mui/material';
import {
  TrendingUp, TrendingDown, TrendingFlat, ArrowForward,
} from '@mui/icons-material';
import { useTherapistBridge } from '../../../../contexts/TherapistClientBridgeContext';
import { OutcomeOverview, OutcomeTrendEntry } from '../../../../types/therapistClientBridge';

interface Props {
  clientId: string;
}

// ── Chart helpers ──────────────────────────────────────────────────

const CHART_W = 720;
const CHART_H = 220;
const PAD_X = 50;
const PAD_Y = 30;

function pathFromPoints(pts: { x: number; y: number }[]): string {
  if (!pts.length) return '';
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
}

const SERIES_COLORS = ['#0b57d0', '#c05a01', '#10b981', '#7e57c2', '#d84315'];

const SEVERITY_TO_RANK: Record<string, number> = {
  'Minimal': 0, 'Mild': 1, 'Moderate': 2, 'Moderately Severe': 3, 'Severe': 4,
};

// ── Component ──────────────────────────────────────────────────────

export const TrendsPanel: React.FC<Props> = ({ clientId }) => {
  const bridge = useTherapistBridge();
  const [overview, setOverview] = useState<OutcomeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    bridge.getClientPortalOverview(clientId)
      .then(o => setOverview(o.outcomeOverview))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [clientId, bridge]);

  // Group trend entries by measure ID, sorted by date ascending
  const grouped = useMemo<Record<string, OutcomeTrendEntry[]>>(() => {
    const o = overview;
    if (!o?.trend?.length) return {};
    const out: Record<string, OutcomeTrendEntry[]> = {};
    for (const t of o.trend) {
      if (!out[t.measureId]) out[t.measureId] = [];
      out[t.measureId].push(t);
    }
    for (const k of Object.keys(out)) {
      out[k] = out[k].sort((a, b) => a.weekOf.localeCompare(b.weekOf));
    }
    return out;
  }, [overview]);

  if (loading) {
    return (
      <Stack spacing={2}>
        <Skeleton variant="rounded" height={CHART_H} />
        <Skeleton variant="rounded" height={140} />
      </Stack>
    );
  }
  if (error) return <Alert severity="error">Could not load trends: {error}</Alert>;
  if (!overview || !Object.keys(grouped).length) {
    return (
      <Alert severity="info">
        Once the patient completes their first questionnaire, trends will appear here.
      </Alert>
    );
  }

  const measureIds = Object.keys(grouped);

  // ── Chart geometry ──────────────────────────────────────────────
  // X axis = combined week range across all measures
  const allDates = Object.values(grouped).flat().map(t => t.weekOf).sort();
  const xDomain = [allDates[0], allDates[allDates.length - 1]];

  const dateToX = (date: string) => {
    if (xDomain[0] === xDomain[1]) return PAD_X + (CHART_W - 2 * PAD_X) / 2;
    const totalDays = Math.max(1, daysBetween(xDomain[0], xDomain[1]));
    const days = daysBetween(xDomain[0], date);
    return PAD_X + (days / totalDays) * (CHART_W - 2 * PAD_X);
  };

  // Y is normalized 0..1 (score / maxScore) so we can overlay measures of different scales
  const yFromNormalized = (n: number) => PAD_Y + (1 - n) * (CHART_H - 2 * PAD_Y);

  // ── Sections ────────────────────────────────────────────────────
  return (
    <Stack spacing={3}>
      {/* OVERLAY CHART */}
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" component="div" sx={{ fontWeight: 600, mb: 0.5 }}>
            Symptoms Over Time
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            All measures normalized to 0–100% of max score. Lower is better.
          </Typography>

          <Box sx={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
            <svg width={CHART_W} height={CHART_H} style={{ display: 'block', maxWidth: '100%' }}>
              {/* Grid */}
              {[0, 0.25, 0.5, 0.75, 1].map(g => {
                const y = yFromNormalized(g);
                return (
                  <g key={g}>
                    <line x1={PAD_X} x2={CHART_W - PAD_X} y1={y} y2={y} stroke="#eee" />
                    <text x={PAD_X - 8} y={y + 4} fontSize="10" textAnchor="end" fill="#999">
                      {Math.round(g * 100)}%
                    </text>
                  </g>
                );
              })}

              {/* Series */}
              {measureIds.map((mid, mi) => {
                const series = grouped[mid];
                const color = SERIES_COLORS[mi % SERIES_COLORS.length];
                const pts = series.map(t => ({
                  x: dateToX(t.weekOf),
                  y: yFromNormalized(t.score / Math.max(1, t.maxScore)),
                }));
                return (
                  <g key={mid}>
                    <path d={pathFromPoints(pts)} fill="none" stroke={color} strokeWidth={2.5} />
                    {pts.map((p, i) => (
                      <circle key={i} cx={p.x} cy={p.y} r={3.5} fill={color} stroke="#fff" strokeWidth={1.5} />
                    ))}
                  </g>
                );
              })}

              {/* X-axis labels (first, middle, last) */}
              {[allDates[0], allDates[Math.floor(allDates.length / 2)], allDates[allDates.length - 1]].map(d => (
                <text key={d} x={dateToX(d)} y={CHART_H - 8} fontSize="10" textAnchor="middle" fill="#666">
                  {formatShortDate(d)}
                </text>
              ))}
            </svg>
          </Box>

          {/* Legend */}
          <Stack direction="row" spacing={2} sx={{ mt: 1.5 }} useFlexGap flexWrap="wrap">
            {measureIds.map((mid, mi) => {
              const series = grouped[mid];
              return (
                <Stack key={mid} direction="row" spacing={1} alignItems="center">
                  <Box sx={{ width: 12, height: 12, bgcolor: SERIES_COLORS[mi % SERIES_COLORS.length], borderRadius: 0.5 }} />
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    {series[0].measureShortName}
                  </Typography>
                </Stack>
              );
            })}
          </Stack>
        </CardContent>
      </Card>

      {/* DELTA CARDS */}
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
          CHANGE SINCE START
        </Typography>
        <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap">
          {measureIds.map(mid => {
            const series = grouped[mid];
            const first = series[0];
            const last = series[series.length - 1];
            const prev = series[series.length - 2] || first;
            const sinceStart = last.score - first.score;
            const sinceLast = last.score - prev.score;
            return (
              <Card key={mid} variant="outlined" sx={{ minWidth: 240, flex: '1 1 240px' }}>
                <CardContent>
                  <Stack direction="row" alignItems="center" justifyContent="space-between">
                    <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                      {last.measureShortName}
                    </Typography>
                    <Chip
                      size="small"
                      label={last.severity}
                      color={last.severityColor}
                      variant="outlined"
                    />
                  </Stack>
                  <Stack direction="row" alignItems="baseline" spacing={0.5} sx={{ mt: 1 }}>
                    <Typography variant="h4" component="div" sx={{ fontWeight: 700 }}>
                      {last.score}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      / {last.maxScore}
                    </Typography>
                  </Stack>
                  <Stack direction="row" spacing={2} sx={{ mt: 1.5 }}>
                    <DeltaCell label="vs Start" delta={sinceStart} good={sinceStart < 0} />
                    <DeltaCell label="vs Last" delta={sinceLast} good={sinceLast < 0} />
                  </Stack>
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      </Box>

      {/* SEVERITY TRANSITIONS */}
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
          SEVERITY TRANSITIONS
        </Typography>
        <Card variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Measure</TableCell>
                <TableCell>From</TableCell>
                <TableCell />
                <TableCell>To</TableCell>
                <TableCell>Direction</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {findTransitions(grouped).map((tr, i) => (
                <TableRow key={i}>
                  <TableCell>{formatShortDate(tr.weekOf)}</TableCell>
                  <TableCell>{tr.measureShortName}</TableCell>
                  <TableCell>
                    <Chip size="small" label={tr.from} color={severityColor(tr.from)} variant="outlined" />
                  </TableCell>
                  <TableCell><ArrowForward fontSize="small" sx={{ color: 'text.secondary' }} /></TableCell>
                  <TableCell>
                    <Chip size="small" label={tr.to} color={severityColor(tr.to)} variant="outlined" />
                  </TableCell>
                  <TableCell>
                    {tr.improving ? (
                      <TrendingDown sx={{ color: 'success.main', fontSize: 18 }} />
                    ) : (
                      <TrendingUp sx={{ color: 'error.main', fontSize: 18 }} />
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {findTransitions(grouped).length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography variant="caption" color="text.secondary">
                      No severity bucket changes yet.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </Card>
      </Box>
    </Stack>
  );
};

// ── Sub-components ──────────────────────────────────────────────────

const DeltaCell: React.FC<{ label: string; delta: number; good: boolean }> = ({ label, delta, good }) => {
  const Icon = delta === 0 ? TrendingFlat : delta < 0 ? TrendingDown : TrendingUp;
  const color = delta === 0 ? 'text.secondary' : good ? 'success.main' : 'error.main';
  const sign = delta > 0 ? '+' : '';
  return (
    <Stack flex={1}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Stack direction="row" alignItems="center" spacing={0.5}>
        <Icon sx={{ color, fontSize: 18 }} />
        <Typography variant="body2" sx={{ fontWeight: 600, color }}>
          {sign}{delta}
        </Typography>
      </Stack>
    </Stack>
  );
};

// ── Pure helpers ────────────────────────────────────────────────────

function findTransitions(
  grouped: Record<string, OutcomeTrendEntry[]>
): Array<{ weekOf: string; measureShortName: string; from: string; to: string; improving: boolean }> {
  const out: Array<{ weekOf: string; measureShortName: string; from: string; to: string; improving: boolean }> = [];
  for (const series of Object.values(grouped)) {
    for (let i = 1; i < series.length; i++) {
      const prev = series[i - 1];
      const cur = series[i];
      if (prev.severity !== cur.severity) {
        const prevRank = SEVERITY_TO_RANK[prev.severity] ?? 0;
        const curRank = SEVERITY_TO_RANK[cur.severity] ?? 0;
        out.push({
          weekOf: cur.weekOf,
          measureShortName: cur.measureShortName,
          from: prev.severity,
          to: cur.severity,
          improving: curRank < prevRank,
        });
      }
    }
  }
  return out.sort((a, b) => b.weekOf.localeCompare(a.weekOf));
}

function severityColor(s: string): 'success' | 'info' | 'warning' | 'error' | 'default' {
  const r = SEVERITY_TO_RANK[s];
  if (r === 0) return 'success';
  if (r === 1) return 'info';
  if (r === 2) return 'warning';
  if (r >= 3) return 'error';
  return 'default';
}

function daysBetween(a: string, b: string): number {
  const da = new Date(a);
  const db = new Date(b);
  return Math.round((db.getTime() - da.getTime()) / (1000 * 60 * 60 * 24));
}

function formatShortDate(d: string): string {
  if (!d) return '';
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default TrendsPanel;
