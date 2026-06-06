"""
Pydantic models mirroring frontend/types/therapistClientBridge.ts and clientPortal.ts.

Used for request body validation. Optional fields permitted; backend fills server-side fields
(id, assignedAt, etc.) before writing to Firestore.
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict

# ── Homework ────────────────────────────────────────────────────────

HomeworkStatus = Literal['ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED']


class HomeworkUpsert(BaseModel):
    """Body of POST /portal/clients/{id}/homework"""
    model_config = ConfigDict(extra='forbid')

    moduleId: str
    moduleTitle: str
    moduleCategory: str
    estimatedMinutes: int = Field(ge=0)
    dueAt: Optional[str] = None
    status: HomeworkStatus = 'ASSIGNED'
    note: Optional[str] = None
    sourceSessionId: Optional[str] = None
    sourceSessionDate: Optional[str] = None


class HomeworkStatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: HomeworkStatus


class HomeworkPatch(BaseModel):
    """Body of PATCH /portal/clients/{id}/homework/{hwId} — full update incl. reschedule."""
    model_config = ConfigDict(extra='forbid')
    dueAt: Optional[str] = None
    note: Optional[str] = None
    status: Optional[HomeworkStatus] = None


# ── Interventions ──────────────────────────────────────────────────

InterventionFrequency = Literal['DAILY', 'TWICE_DAILY', 'AS_NEEDED', 'WEEKLY']
InterventionStatus = Literal['ACTIVE', 'ARCHIVED']


class InterventionUpsert(BaseModel):
    model_config = ConfigDict(extra='forbid')
    interventionId: str
    interventionTitle: str
    interventionType: str
    frequency: Optional[InterventionFrequency] = None
    dueAt: Optional[str] = None
    status: InterventionStatus = 'ACTIVE'
    note: Optional[str] = None


# ── Publish Draft ──────────────────────────────────────────────────

class PublishSections(BaseModel):
    themes: bool = False
    keyMoments: bool = False
    homeworkList: bool = False
    riskLabel: bool = False
    nextSteps: bool = False


class PublishDraftPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sections: PublishSections


# ── Activity Events ────────────────────────────────────────────────

ActivityEventType = Literal[
    'HOMEWORK_ASSIGNED', 'HOMEWORK_COMPLETED', 'HOMEWORK_ARCHIVED', 'HOMEWORK_RESCHEDULED',
    'INTERVENTION_ASSIGNED', 'INTERVENTION_ARCHIVED',
    'SUMMARY_PUBLISHED', 'SUMMARY_UNPUBLISHED',
    'MODULE_SENT',
    'QUESTIONNAIRE_ASSIGNED', 'QUESTIONNAIRE_PAUSED', 'QUESTIONNAIRE_REMOVED',
    'QUESTIONNAIRE_COMPLETED',
]


class ActivityEventCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: ActivityEventType
    description: str
    actor: Literal['therapist', 'client']


# ── Questionnaires ─────────────────────────────────────────────────

QuestionnaireCadence = Literal['WEEKLY', 'BIWEEKLY', 'MONTHLY', 'SESSION']
QuestionnaireStatus = Literal['ACTIVE', 'PAUSED', 'REMOVED']


class QuestionnaireAssign(BaseModel):
    model_config = ConfigDict(extra='forbid')
    questionnaireId: str
    cadence: QuestionnaireCadence
    note: Optional[str] = None


class QuestionnaireStatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: QuestionnaireStatus


class QuestionnaireResponseSubmit(BaseModel):
    """Body of POST /portal/me/questionnaires/{aId}/responses"""
    model_config = ConfigDict(extra='forbid')
    weekOf: str  # 'YYYY-MM-DD'
    items: List[dict]  # [{itemIndex, value, label?}]
    totalScore: int = Field(ge=0)
    maxScore: int = Field(gt=0)


# ── Journal ─────────────────────────────────────────────────────────

class JournalEntryUpsert(BaseModel):
    """Body of POST /portal/me/journal (id optional — upsert semantics)."""
    model_config = ConfigDict(extra='forbid')
    id: Optional[str] = None
    date: Optional[str] = None
    moduleId: Optional[str] = None
    interventionId: Optional[str] = None
    sessionId: Optional[str] = None
    keyInsights: str = ''
    personalApplication: str = ''
    discussionTopics: str = ''


# ── Outcome Responses (patient) ────────────────────────────────────

class OutcomeResponseSubmit(BaseModel):
    """Body of POST /portal/me/outcome-responses"""
    model_config = ConfigDict(extra='forbid')
    measureId: str
    weekOf: str
    responses: List[int]
    score: int = Field(ge=0)


# ── Intervention Session (patient running an intervention) ─────────

class InterventionSessionStart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    interventionId: str
