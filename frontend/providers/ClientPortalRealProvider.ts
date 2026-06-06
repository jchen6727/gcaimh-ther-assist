/**
 * Real Provider — Patient Client Portal (/portal/me/*)
 *
 * Calls the backend portal API. Activated when VITE_USE_MOCK_PROVIDER !== 'true'.
 *
 * patient_id is derived server-side from the Firebase token; never passed by the client.
 */
import { portalApi } from './portalApiClient';
import {
  HomeworkAssignment, HomeworkStatus, PsychoeducationModule, Intervention, InterventionSession,
  JournalEntry, ClientProgress, TherapySession, IntegrativeAnalysis,
  OutcomeMeasure, OutcomeResponse, OutcomeSchedule,
} from '../types/clientPortal';

/**
 * Minimal interface restated here to avoid circular import with ClientPortalContext.
 * Must stay in sync with ClientPortalProvider in ClientPortalContext.tsx.
 */
interface ClientPortalProvider {
  listModules(): Promise<PsychoeducationModule[]>;
  listHomeworkAssignments(): Promise<HomeworkAssignment[]>;
  listInterventions(): Promise<Intervention[]>;
  updateHomeworkStatus(assignmentId: string, status: HomeworkStatus): Promise<void>;
  getClientProgress(): Promise<ClientProgress>;
  listJournalEntries(): Promise<JournalEntry[]>;
  upsertJournalEntry(entry: Partial<JournalEntry>): Promise<JournalEntry>;
  getIntegrativeAnalysis(): Promise<IntegrativeAnalysis>;
  listTherapySessions(): Promise<TherapySession[]>;
  listOutcomeMeasures(): Promise<OutcomeMeasure[]>;
  getOutcomeSchedule(): Promise<OutcomeSchedule>;
  listOutcomeResponses(measureId: string, limit?: number): Promise<OutcomeResponse[]>;
  submitOutcomeResponse(response: { measureId: string; weekOf: string; responses: number[]; score: number }): Promise<OutcomeResponse>;
  startInterventionSession(interventionId: string): Promise<InterventionSession>;
}

export function createRealClientPortalProvider(): ClientPortalProvider {
  return {
    // ── P1 — uses catalog (shared with therapist) ────────────────────
    async listModules(): Promise<PsychoeducationModule[]> {
      return portalApi.get('/portal/catalog/modules');
    },

    // ── P2 ──────────────────────────────────────────────────────────
    async listHomeworkAssignments(): Promise<HomeworkAssignment[]> {
      return portalApi.get('/portal/me/homework');
    },

    // ── P3 ──────────────────────────────────────────────────────────
    async listInterventions(): Promise<Intervention[]> {
      return portalApi.get('/portal/me/interventions');
    },

    // ── P4 ──────────────────────────────────────────────────────────
    async updateHomeworkStatus(assignmentId: string, status: HomeworkStatus): Promise<void> {
      await portalApi.patch(
        `/portal/me/homework/${encodeURIComponent(assignmentId)}/status`,
        { status },
      );
    },

    // ── P5 ──────────────────────────────────────────────────────────
    async getClientProgress(): Promise<ClientProgress> {
      return portalApi.get('/portal/me/progress');
    },

    // ── P6 ──────────────────────────────────────────────────────────
    async listJournalEntries(): Promise<JournalEntry[]> {
      return portalApi.get('/portal/me/journal');
    },

    // ── P7 ──────────────────────────────────────────────────────────
    async upsertJournalEntry(entry: Partial<JournalEntry>): Promise<JournalEntry> {
      return portalApi.post('/portal/me/journal', entry);
    },

    // ── P8 ──────────────────────────────────────────────────────────
    async getIntegrativeAnalysis(): Promise<IntegrativeAnalysis> {
      return portalApi.get('/portal/me/integrative-analysis');
    },

    // ── P9 ──────────────────────────────────────────────────────────
    async listTherapySessions(): Promise<TherapySession[]> {
      return portalApi.get('/portal/me/sessions');
    },

    // ── P10 ─────────────────────────────────────────────────────────
    async listOutcomeMeasures(): Promise<OutcomeMeasure[]> {
      return portalApi.get('/portal/me/outcome-measures');
    },

    // ── P11 ─────────────────────────────────────────────────────────
    async getOutcomeSchedule(): Promise<OutcomeSchedule> {
      return portalApi.get('/portal/me/outcome-schedule');
    },

    // ── P12 ─────────────────────────────────────────────────────────
    async listOutcomeResponses(measureId: string, limit?: number): Promise<OutcomeResponse[]> {
      return portalApi.get('/portal/me/outcome-responses', {
        measureId,
        ...(limit !== undefined ? { limit } : {}),
      });
    },

    // ── P13 ─────────────────────────────────────────────────────────
    async submitOutcomeResponse(
      response: { measureId: string; weekOf: string; responses: number[]; score: number },
    ): Promise<OutcomeResponse> {
      return portalApi.post('/portal/me/outcome-responses', response);
    },

    // ── P14 ─────────────────────────────────────────────────────────
    async startInterventionSession(interventionId: string): Promise<InterventionSession> {
      return portalApi.post('/portal/me/intervention-sessions', { interventionId });
    },
  };
}
