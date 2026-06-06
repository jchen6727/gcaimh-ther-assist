/**
 * Real Provider — Therapist ↔ Client Portal Bridge
 *
 * Calls the backend portal API (storage-access-function /portal/*).
 * Activated when VITE_USE_MOCK_PROVIDER !== 'true'.
 */
import { portalApi } from './portalApiClient';
import {
  TherapistClientBridgeProvider,
  BridgeClient,
  ClientPortalOverview,
  TherapistHomeworkItem,
  HomeworkBridgeStatus,
  TherapistInterventionAssignment,
  PublishDraft,
  ActivityEvent,
  ModuleForAssignment,
  InterventionForAssignment,
  QuestionnaireDefinition,
  QuestionnaireAssignment,
  QuestionnaireResponse,
  QuestionnaireCadence,
  QuestionnaireStatus,
} from '../types/therapistClientBridge';

export class TherapistClientBridgeRealProvider implements TherapistClientBridgeProvider {
  // ── Clients ───────────────────────────────────────────────────────
  async listClients(): Promise<BridgeClient[]> {
    return portalApi.get('/portal/clients');
  }

  async getClientPortalOverview(clientId: string): Promise<ClientPortalOverview> {
    return portalApi.get(`/portal/clients/${encodeURIComponent(clientId)}/overview`);
  }

  // ── Homework ──────────────────────────────────────────────────────
  async listClientHomework(clientId: string): Promise<TherapistHomeworkItem[]> {
    return portalApi.get(`/portal/clients/${encodeURIComponent(clientId)}/homework`);
  }

  async upsertHomework(
    clientId: string,
    payload: Omit<TherapistHomeworkItem, 'id' | 'clientId' | 'assignedAt'>,
  ): Promise<TherapistHomeworkItem> {
    return portalApi.post(`/portal/clients/${encodeURIComponent(clientId)}/homework`, payload);
  }

  async updateHomeworkStatus(
    clientId: string,
    homeworkId: string,
    status: HomeworkBridgeStatus,
  ): Promise<void> {
    await portalApi.patch(
      `/portal/clients/${encodeURIComponent(clientId)}/homework/${encodeURIComponent(homeworkId)}/status`,
      { status },
    );
  }

  // ── Interventions ────────────────────────────────────────────────
  async listClientInterventions(clientId: string): Promise<TherapistInterventionAssignment[]> {
    return portalApi.get(`/portal/clients/${encodeURIComponent(clientId)}/interventions`);
  }

  async assignIntervention(
    clientId: string,
    payload: Omit<TherapistInterventionAssignment, 'id' | 'clientId' | 'assignedAt'>,
  ): Promise<TherapistInterventionAssignment> {
    return portalApi.post(`/portal/clients/${encodeURIComponent(clientId)}/interventions`, payload);
  }

  async archiveIntervention(clientId: string, assignmentId: string): Promise<void> {
    await portalApi.del(
      `/portal/clients/${encodeURIComponent(clientId)}/interventions/${encodeURIComponent(assignmentId)}`,
    );
  }

  // ── Publish Drafts ────────────────────────────────────────────────
  async getPublishDraft(clientId: string): Promise<PublishDraft | null> {
    return portalApi.get(`/portal/clients/${encodeURIComponent(clientId)}/publish-draft`);
  }

  async updatePublishDraft(
    clientId: string,
    draftId: string,
    patch: Partial<Pick<PublishDraft, 'sections'>>,
  ): Promise<PublishDraft> {
    return portalApi.patch(
      `/portal/clients/${encodeURIComponent(clientId)}/publish-draft/${encodeURIComponent(draftId)}`,
      patch,
    );
  }

  async publishToClient(clientId: string, draftId: string): Promise<void> {
    await portalApi.post(
      `/portal/clients/${encodeURIComponent(clientId)}/publish-draft/${encodeURIComponent(draftId)}/publish`,
    );
  }

  async unpublishFromClient(clientId: string, draftId: string): Promise<void> {
    await portalApi.post(
      `/portal/clients/${encodeURIComponent(clientId)}/publish-draft/${encodeURIComponent(draftId)}/unpublish`,
    );
  }

  // ── Activity ──────────────────────────────────────────────────────
  async listActivityEvents(clientId: string): Promise<ActivityEvent[]> {
    return portalApi.get(`/portal/clients/${encodeURIComponent(clientId)}/activity`);
  }

  async addActivityEvent(event: Omit<ActivityEvent, 'id'>): Promise<ActivityEvent> {
    return portalApi.post(
      `/portal/clients/${encodeURIComponent(event.clientId)}/activity`,
      { type: event.type, description: event.description, actor: event.actor },
    );
  }

  // ── Catalog ──────────────────────────────────────────────────────
  async listModulesForAssignment(): Promise<ModuleForAssignment[]> {
    return portalApi.get('/portal/catalog/modules');
  }

  async listInterventionsForAssignment(): Promise<InterventionForAssignment[]> {
    return portalApi.get('/portal/catalog/interventions');
  }

  async listQuestionnaireDefinitions(): Promise<QuestionnaireDefinition[]> {
    return portalApi.get('/portal/catalog/questionnaires');
  }

  // ── Questionnaires ───────────────────────────────────────────────
  async listClientQuestionnaires(clientId: string): Promise<QuestionnaireAssignment[]> {
    return portalApi.get(`/portal/clients/${encodeURIComponent(clientId)}/questionnaires`);
  }

  async assignQuestionnaire(
    clientId: string,
    payload: { questionnaireId: string; cadence: QuestionnaireCadence; note?: string },
  ): Promise<QuestionnaireAssignment> {
    return portalApi.post(`/portal/clients/${encodeURIComponent(clientId)}/questionnaires`, payload);
  }

  async updateQuestionnaireStatus(
    clientId: string,
    assignmentId: string,
    status: QuestionnaireStatus,
  ): Promise<void> {
    await portalApi.patch(
      `/portal/clients/${encodeURIComponent(clientId)}/questionnaires/${encodeURIComponent(assignmentId)}/status`,
      { status },
    );
  }

  async listQuestionnaireResponses(
    clientId: string,
    assignmentId: string,
  ): Promise<QuestionnaireResponse[]> {
    return portalApi.get(
      `/portal/clients/${encodeURIComponent(clientId)}/questionnaires/${encodeURIComponent(assignmentId)}/responses`,
    );
  }
}
