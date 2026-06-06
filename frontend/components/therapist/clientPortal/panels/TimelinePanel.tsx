/**
 * TimelinePanel — chronological feed of EVERYTHING the patient has done.
 *
 * Pulls from 5 data sources via the TherapistClientBridge and merges them
 * into a single date-sorted event stream:
 *   - Past therapy sessions
 *   - Homework assignments + completions
 *   - Journal entries (when bridge eventually exposes them)
 *   - Intervention sessions (when bridge eventually exposes them)
 *   - Therapist activity events (assigned X, published summary, etc.)
 *
 * Filter chips at top let the therapist focus on one event type at a time.
 * Sticky date headers group events by month.
 *
 * In production this is one of the highest-value views — it shows the patient's
 * arc at a glance: sessions → homework → engagement → next session.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Box, Card, Stack, Typography, Chip, CircularProgress, Avatar,
  IconButton, Collapse, Divider, Tooltip,
} from '@mui/material';
import {
  Event, Assignment, CheckCircle, Archive, Publish, Quiz,
  ArrowForwardIos, ExpandMore, ExpandLess, EditNote, History,
  PsychologyAlt, MedicalServices,
} from '@mui/icons-material';
import { useTherapistBridge } from '../../../../contexts/TherapistClientBridgeContext';
import {
  TherapistHomeworkItem,
  ActivityEvent,
  ActivityEventType,
} from '../../../../types/therapistClientBridge';

// ── Unified Timeline Event ──────────────────────────────────────────

type EventType =
  | 'session'
  | 'homework_assigned'
  | 'homework_completed'
  | 'homework_archived'
  | 'questionnaire_completed'
  | 'questionnaire_assigned'
  | 'summary_published'
  | 'intervention_assigned'
  | 'other';

interface TimelineEvent {
  id: string;
  date: string;            // ISO
  type: EventType;
  title: string;
  subtitle?: string;
  details?: string;
  meta?: Record<string, string | number | undefined>;
  actor: 'therapist' | 'client' | 'system';
}

// ── Visual config per event type ────────────────────────────────────

const EVENT_CONFIG: Record<EventType, {
  color: string;
  icon: React.ReactElement;
  label: string;
}> = {
  session:                 { color: '#0b57d0', icon: <Event fontSize="small" />,          label: 'Session' },
  homework_assigned:       { color: '#7e57c2', icon: <Assignment fontSize="small" />,     label: 'Homework Assigned' },
  homework_completed:      { color: '#43a047', icon: <CheckCircle fontSize="small" />,    label: 'Homework Done' },
  homework_archived:       { color: '#9e9e9e', icon: <Archive fontSize="small" />,        label: 'Homework Archived' },
  questionnaire_completed: { color: '#0288d1', icon: <Quiz fontSize="small" />,           label: 'Questionnaire Done' },
  questionnaire_assigned:  { color: '#5e35b1', icon: <Quiz fontSize="small" />,           label: 'Questionnaire Assigned' },
  summary_published:       { color: '#00838f', icon: <Publish fontSize="small" />,        label: 'Summary Published' },
  intervention_assigned:   { color: '#d84315', icon: <PsychologyAlt fontSize="small" />,  label: 'Intervention Assigned' },
  other:                   { color: '#616161', icon: <History fontSize="small" />,        label: 'Other' },
};

// ── Activity event type → timeline event type ──────────────────────

const ACTIVITY_TO_TIMELINE: Partial<Record<ActivityEventType, EventType>> = {
  HOMEWORK_ASSIGNED: 'homework_assigned',
  HOMEWORK_COMPLETED: 'homework_completed',
  HOMEWORK_ARCHIVED: 'homework_archived',
  INTERVENTION_ASSIGNED: 'intervention_assigned',
  SUMMARY_PUBLISHED: 'summary_published',
  QUESTIONNAIRE_ASSIGNED: 'questionnaire_assigned',
  QUESTIONNAIRE_COMPLETED: 'questionnaire_completed',
};

// ── Component ───────────────────────────────────────────────────────

interface Props {
  clientId: string;
  refreshKey?: number;
}

export const TimelinePanel: React.FC<Props> = ({ clientId, refreshKey }) => {
  const bridge = useTherapistBridge();
  const [loading, setLoading] = useState(true);
  const [homework, setHomework] = useState<TherapistHomeworkItem[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [activeFilters, setActiveFilters] = useState<Set<EventType>>(new Set());
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      bridge.listClientHomework(clientId),
      bridge.listActivityEvents(clientId),
    ]).then(([hw, act]) => {
      setHomework(hw);
      setActivity(act);
    }).finally(() => setLoading(false));
  }, [clientId, refreshKey, bridge]);

  // ── Merge into unified event stream ──────────────────────────────
  const events = useMemo<TimelineEvent[]>(() => {
    const out: TimelineEvent[] = [];

    // Homework: synthesize an "assigned" event from the homework doc itself
    // (more reliable than relying on activity log alone, which can miss entries)
    homework.forEach(hw => {
      out.push({
        id: `hw-assigned-${hw.id}`,
        date: hw.assignedAt,
        type: 'homework_assigned',
        title: hw.moduleTitle,
        subtitle: hw.moduleCategory,
        details: hw.note,
        meta: {
          status: hw.status,
          estimatedMin: hw.estimatedMinutes,
          due: hw.dueAt,
          fromSession: hw.sourceSessionDate,
        },
        actor: 'therapist',
      });
      if (hw.progress?.completedAt) {
        out.push({
          id: `hw-completed-${hw.id}`,
          date: hw.progress.completedAt,
          type: 'homework_completed',
          title: hw.moduleTitle,
          subtitle: 'Completed',
          meta: { status: hw.status },
          actor: 'client',
        });
      }
    });

    // Activity log: pull non-homework entries (homework already covered above)
    activity.forEach(a => {
      const mappedType = ACTIVITY_TO_TIMELINE[a.type] ?? 'other';
      // Skip if it's a homework event we already added from homework[]
      if (mappedType === 'homework_assigned' || mappedType === 'homework_completed') return;
      out.push({
        id: `act-${a.id}`,
        date: a.timestamp,
        type: mappedType,
        title: a.description,
        actor: a.actor,
      });
    });

    // Sort DESC (newest first)
    return out.sort((x, y) => (y.date || '').localeCompare(x.date || ''));
  }, [homework, activity]);

  // ── Apply filter chips ───────────────────────────────────────────
  const visibleEvents = activeFilters.size === 0
    ? events
    : events.filter(e => activeFilters.has(e.type));

  // ── Group by month for sticky headers ────────────────────────────
  const groups = useMemo(() => {
    const buckets: { label: string; events: TimelineEvent[] }[] = [];
    let lastKey = '';
    for (const ev of visibleEvents) {
      const d = new Date(ev.date);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      if (key !== lastKey) {
        buckets.push({ label, events: [] });
        lastKey = key;
      }
      buckets[buckets.length - 1].events.push(ev);
    }
    return buckets;
  }, [visibleEvents]);

  const toggleFilter = (t: EventType) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t); else next.add(t);
      return next;
    });
  };

  if (loading) {
    return <Box display="flex" justifyContent="center" p={4}><CircularProgress /></Box>;
  }

  if (!events.length) {
    return (
      <Box p={4} textAlign="center">
        <MedicalServices sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
        <Typography color="text.secondary">No timeline events yet.</Typography>
        <Typography variant="caption" color="text.secondary">
          Run a session, assign homework, or have the client complete an activity.
        </Typography>
      </Box>
    );
  }

  // ── Filter chips ────────────────────────────────────────────────
  const presentTypes = Array.from(new Set(events.map(e => e.type))) as EventType[];

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
          FILTER BY EVENT TYPE
        </Typography>
        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
          {presentTypes.map(t => {
            const cfg = EVENT_CONFIG[t];
            const isActive = activeFilters.has(t);
            const isInactive = activeFilters.size > 0 && !isActive;
            return (
              <Chip
                key={t}
                icon={cfg.icon}
                label={cfg.label}
                onClick={() => toggleFilter(t)}
                sx={{
                  borderColor: cfg.color,
                  color: isInactive ? 'text.disabled' : cfg.color,
                  bgcolor: isActive ? `${cfg.color}15` : 'transparent',
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
                variant="outlined"
              />
            );
          })}
          {activeFilters.size > 0 && (
            <Chip
              label={`Clear filters (${activeFilters.size})`}
              onClick={() => setActiveFilters(new Set())}
              size="small"
              variant="outlined"
            />
          )}
        </Stack>
      </Box>

      <Typography variant="caption" color="text.secondary">
        Showing {visibleEvents.length} of {events.length} events
      </Typography>

      {/* Timeline */}
      {groups.map((g, gi) => (
        <Box key={g.label}>
          {/* Month header */}
          <Box sx={{
            position: 'sticky', top: 0, zIndex: 1, py: 1, mb: 1,
            bgcolor: 'background.default',
            borderBottom: '1px solid', borderColor: 'divider',
          }}>
            <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 600 }}>
              {g.label}
            </Typography>
          </Box>

          <Stack spacing={1.5} sx={{ position: 'relative', pl: 4 }}>
            {/* Vertical timeline line */}
            <Box sx={{
              position: 'absolute', left: 15, top: 0, bottom: 0, width: 2,
              bgcolor: 'divider',
            }} />

            {g.events.map(ev => {
              const cfg = EVENT_CONFIG[ev.type];
              const isExpanded = expandedId === ev.id;
              const hasDetails = !!ev.details || (ev.meta && Object.values(ev.meta).some(v => v));
              return (
                <Box key={ev.id} sx={{ position: 'relative' }}>
                  {/* Dot on the timeline */}
                  <Avatar sx={{
                    position: 'absolute', left: -32, top: 8, width: 30, height: 30,
                    bgcolor: cfg.color, boxShadow: 2,
                  }}>
                    {cfg.icon}
                  </Avatar>

                  {/* Card */}
                  <Card variant="outlined" sx={{
                    borderLeft: `4px solid ${cfg.color}`,
                    cursor: hasDetails ? 'pointer' : 'default',
                    transition: 'background-color 0.2s',
                    '&:hover': hasDetails ? { bgcolor: 'action.hover' } : {},
                  }}
                  onClick={() => hasDetails && setExpandedId(isExpanded ? null : ev.id)}
                  >
                    <Stack direction="row" alignItems="center" spacing={1.5} sx={{ p: 1.5 }}>
                      <Box flex={1}>
                        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.25 }}>
                          <Tooltip title={cfg.label}>
                            <Chip
                              label={cfg.label}
                              size="small"
                              sx={{ bgcolor: `${cfg.color}15`, color: cfg.color, fontWeight: 600, height: 22 }}
                            />
                          </Tooltip>
                          <Typography variant="caption" color="text.secondary">
                            {formatRelativeDate(ev.date)}
                          </Typography>
                          {ev.actor === 'client' && (
                            <Chip label="client" size="small" variant="outlined" sx={{ height: 18, fontSize: '10px' }} />
                          )}
                        </Stack>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {ev.title}
                        </Typography>
                        {ev.subtitle && (
                          <Typography variant="caption" color="text.secondary">
                            {ev.subtitle}
                          </Typography>
                        )}
                      </Box>
                      {hasDetails && (
                        <IconButton size="small">
                          {isExpanded ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
                        </IconButton>
                      )}
                    </Stack>

                    <Collapse in={isExpanded} unmountOnExit>
                      <Divider />
                      <Box sx={{ p: 2, bgcolor: 'grey.50' }}>
                        {ev.details && (
                          <Typography variant="body2" sx={{ mb: 1, whiteSpace: 'pre-wrap' }}>
                            {ev.details}
                          </Typography>
                        )}
                        {ev.meta && Object.entries(ev.meta).filter(([, v]) => v).map(([k, v]) => (
                          <Box key={k} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.25 }}>
                            <Typography variant="caption" color="text.secondary" sx={{ textTransform: 'capitalize' }}>
                              {k.replace(/([A-Z])/g, ' $1').trim()}
                            </Typography>
                            <Typography variant="caption" sx={{ fontWeight: 500 }}>
                              {String(v)}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    </Collapse>
                  </Card>
                </Box>
              );
            })}
          </Stack>
        </Box>
      ))}
    </Stack>
  );
};

function formatRelativeDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return `Today · ${d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default TimelinePanel;
