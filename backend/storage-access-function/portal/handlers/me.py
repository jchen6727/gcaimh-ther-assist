"""
Patient self-service endpoints (/portal/me/*).

ALL endpoints derive patient_id from the token (g.user.patientId), NEVER from the URL or body.
This is the privacy boundary that prevents cross-patient data leaks.

Maps to ClientPortalProvider methods:
  P1  listModules()                  → shared catalog.list_modules (handled in router)
  P2  listHomeworkAssignments()      → list_homework
  P3  listInterventions()            → list_interventions
  P4  updateHomeworkStatus(...)      → update_homework_status
  P5  getClientProgress()            → progress
  P6  listJournalEntries()           → list_journal
  P7  upsertJournalEntry(...)        → upsert_journal
  P8  getIntegrativeAnalysis()       → integrative_analysis
  P9  listTherapySessions()          → list_sessions
  P10 listOutcomeMeasures()          → list_outcome_measures
  P11 getOutcomeSchedule()           → outcome_schedule
  P12 listOutcomeResponses(...)      → list_outcome_responses
  P13 submitOutcomeResponse(...)     → submit_outcome_response
  P14 startInterventionSession(...)  → start_intervention_session
"""
from datetime import datetime, timezone
from flask import request, g
from pydantic import ValidationError
from ..auth import require_role, derive_self_patient_id
from ..helpers import (
    db, ok, err, emit_activity, parse_pagination,
    questionnaire_def_doc_to_outcome_measure,
    session_doc_to_therapy_session_patient_view,
    response_doc_to_outcome_response,
)
from ..models import (
    HomeworkStatusUpdate, JournalEntryUpsert,
    OutcomeResponseSubmit, InterventionSessionStart,
)
from . import journal as journal_helpers


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _patient_or_403():
    pid = derive_self_patient_id()
    if not pid:
        return None, err('No patient profile linked to this account', 403)
    return pid, None


# ── P2 listHomeworkAssignments ──────────────────────────────────────

@require_role('patient')
def list_homework():
    pid, e = _patient_or_403()
    if e:
        return e
    docs = db().collection('patients').document(pid).collection('homework').stream()
    return ok([{'id': d.id, **(d.to_dict() or {})} for d in docs])


# ── P4 updateHomeworkStatus ─────────────────────────────────────────

@require_role('patient')
def update_homework_status(hw_id: str):
    pid, e = _patient_or_403()
    if e:
        return e
    try:
        payload = HomeworkStatusUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as ve:
        return err(f'Invalid body: {ve.errors()}', 400)

    ref = db().collection('patients').document(pid).collection('homework').document(hw_id)
    snap = ref.get()
    if not snap.exists:
        return err('Homework not found', 404)
    ref.update({'status': payload.status})
    if payload.status == 'COMPLETED':
        title = (snap.to_dict() or {}).get('moduleTitle', hw_id)
        emit_activity(pid, 'HOMEWORK_COMPLETED', f"Completed homework: {title}", 'client')
    return ok({'success': True})


# ── P3 listInterventions (assigned to this patient) ────────────────

@require_role('patient')
def list_interventions():
    pid, e = _patient_or_403()
    if e:
        return e
    # Patient sees their assigned interventions joined with catalog info
    assignments = list(db().collection('patients').document(pid)
                       .collection('interventionAssignments').stream())
    result = []
    catalog_cache = {}
    for a in assignments:
        ad = a.to_dict() or {}
        if ad.get('status') == 'ARCHIVED':
            continue
        iid = ad.get('interventionId')
        if iid and iid not in catalog_cache:
            cdoc = db().collection('interventions').document(iid).get()
            catalog_cache[iid] = cdoc.to_dict() if cdoc.exists else {}
        cd = catalog_cache.get(iid, {}) or {}
        result.append({
            'id': iid,
            'title': cd.get('title') or ad.get('interventionTitle', ''),
            'type': cd.get('type') or ad.get('interventionType', ''),
            'description': cd.get('description', ''),
            'durationSeconds': cd.get('durationSeconds', 0),
            'frequency': ad.get('frequency'),
        })
    return ok(result)


# ── P5 getClientProgress ────────────────────────────────────────────

@require_role('patient')
def progress():
    pid, e = _patient_or_403()
    if e:
        return e
    base = db().collection('patients').document(pid)
    homework_docs = list(base.collection('homework').stream())
    completed = sum(1 for d in homework_docs if (d.to_dict() or {}).get('status') == 'COMPLETED')
    sessions_count = len(list(base.collection('interventionSessions').stream()))
    journal_count = len(list(base.collection('journal').stream()))
    # totalInterventionMinutes computed from interventionSessions (durationSeconds → minutes)
    total_seconds = sum((d.to_dict() or {}).get('durationSeconds', 0)
                       for d in base.collection('interventionSessions').stream())
    return ok({
        'completedModules': completed,
        'totalAssigned': len(homework_docs),
        'streakDays': 0,  # streak computation deferred — needs daily activity tracking
        'totalInterventionMinutes': total_seconds // 60,
        'journalEntryCount': journal_count,
        'lastActiveAt': _now_iso(),
    })


# ── P6/P7 journal ───────────────────────────────────────────────────

@require_role('patient')
def list_journal():
    pid, e = _patient_or_403()
    if e:
        return e
    after, limit = parse_pagination()
    return ok(journal_helpers.list_entries(pid, after, limit))


@require_role('patient')
def upsert_journal():
    pid, e = _patient_or_403()
    if e:
        return e
    try:
        payload = JournalEntryUpsert.model_validate(request.get_json(silent=True) or {})
    except ValidationError as ve:
        return err(f'Invalid body: {ve.errors()}', 400)
    entry = journal_helpers.upsert_entry(pid, payload.model_dump(exclude_none=True))
    return ok(entry)


# ── P8 integrativeAnalysis ─────────────────────────────────────────

@require_role('patient')
def integrative_analysis():
    pid, e = _patient_or_403()
    if e:
        return e
    doc = db().collection('patients').document(pid) \
        .collection('integrativeAnalysis').document('current').get()
    if not doc.exists:
        # Return a default empty structure rather than null to keep frontend happy
        return ok({
            'overallProgress': '',
            'strengthAreas': [],
            'growthAreas': [],
            'patterns': [],
            'therapeuticInsights': [],
            'recommendations': [],
            'sessionCount': 0,
            'timeframeWeeks': 0,
        })
    return ok(doc.to_dict() or {})


# ── P9 listTherapySessions (patient view) ──────────────────────────

@require_role('patient')
def list_sessions():
    pid, e = _patient_or_403()
    if e:
        return e
    after, limit = parse_pagination()
    coll = db().collection('sessions')
    query = coll.where('patient_id', '==', pid).order_by('date', direction='DESCENDING').limit(limit)
    if after:
        anchor = coll.document(after).get()
        if anchor.exists:
            query = query.start_after(anchor)
    return ok([session_doc_to_therapy_session_patient_view(d) for d in query.stream()])


# ── P10 listOutcomeMeasures ────────────────────────────────────────

@require_role('patient')
def list_outcome_measures():
    """Returns all questionnaire definitions ACTIVE for this patient, as OutcomeMeasure objects."""
    pid, e = _patient_or_403()
    if e:
        return e
    assignments = db().collection('patients').document(pid) \
        .collection('questionnaireAssignments') \
        .where('status', '==', 'ACTIVE').stream()
    measures = []
    seen = set()
    for a in assignments:
        ad = a.to_dict() or {}
        qid = ad.get('questionnaireId')
        if not qid or qid in seen:
            continue
        seen.add(qid)
        defn = db().collection('questionnaireDefinitions').document(qid).get()
        if defn.exists:
            measures.append(questionnaire_def_doc_to_outcome_measure(defn))
    return ok(measures)


# ── P11 getOutcomeSchedule (derived) ───────────────────────────────

@require_role('patient')
def outcome_schedule():
    pid, e = _patient_or_403()
    if e:
        return e
    assignments = db().collection('patients').document(pid) \
        .collection('questionnaireAssignments') \
        .where('status', '==', 'ACTIVE').stream()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    schedule_entries = []
    for a in assignments:
        ad = a.to_dict() or {}
        schedule_entries.append({
            'measureId': ad.get('questionnaireId'),
            'cadence': (ad.get('cadence') or 'weekly').lower(),
            'nextDue': ad.get('nextDueAt') or today,
        })
    return ok({'measures': schedule_entries, 'reminderEnabled': True})


# ── P12 listOutcomeResponses ───────────────────────────────────────

@require_role('patient')
def list_outcome_responses():
    """Query params: measureId (required), limit (optional, default 12)."""
    pid, e = _patient_or_403()
    if e:
        return e
    measure_id = request.args.get('measureId')
    if not measure_id:
        return err('measureId query param required', 400)
    try:
        limit = max(1, min(int(request.args.get('limit', 12)), 200))
    except (TypeError, ValueError):
        limit = 12
    coll = db().collection('patients').document(pid).collection('questionnaireResponses')
    docs = coll.where('questionnaireId', '==', measure_id) \
        .order_by('weekOf', direction='DESCENDING').limit(limit).stream()
    return ok([response_doc_to_outcome_response(d) for d in docs])


# ── P13 submitOutcomeResponse ──────────────────────────────────────

@require_role('patient')
def submit_outcome_response():
    pid, e = _patient_or_403()
    if e:
        return e
    try:
        payload = OutcomeResponseSubmit.model_validate(request.get_json(silent=True) or {})
    except ValidationError as ve:
        return err(f'Invalid body: {ve.errors()}', 400)

    # Find the most recent ACTIVE assignment for this measure to attach to
    assignments = list(db().collection('patients').document(pid)
                       .collection('questionnaireAssignments')
                       .where('questionnaireId', '==', payload.measureId)
                       .where('status', '==', 'ACTIVE').limit(1).stream())
    if not assignments:
        return err(f'No active assignment for measure {payload.measureId}', 404)
    assignment = assignments[0]

    defn = db().collection('questionnaireDefinitions').document(payload.measureId).get()
    if not defn.exists:
        return err('Definition not found', 404)
    d = defn.to_dict() or {}

    # severity bucket
    severity_label = 'Unknown'
    severity_color = 'info'
    for t in d.get('thresholds', []):
        if t.get('min', 0) <= payload.score <= t.get('max', 0):
            severity_label = t.get('label', 'Unknown')
            severity_color = t.get('color', 'info')
            break

    # doc id pattern prevents duplicate weekly submissions
    doc_id = f"{assignment.id}_{payload.weekOf}"
    response_data = {
        'clientId': pid,
        'assignmentId': assignment.id,
        'questionnaireId': payload.measureId,
        'questionnaireName': d.get('name', ''),
        'weekOf': payload.weekOf,
        'completedAt': _now_iso(),
        'items': [{'itemIndex': i, 'value': v} for i, v in enumerate(payload.responses)],
        'totalScore': payload.score,
        'maxScore': d.get('maxScore', 0),
        'severity': severity_label,
        'severityColor': severity_color,
        'flagged': False,
    }
    db().collection('patients').document(pid).collection('questionnaireResponses') \
        .document(doc_id).set(response_data)

    # Increment completion count on assignment
    assignment.reference.update({
        'completionCount': (assignment.to_dict() or {}).get('completionCount', 0) + 1,
        'lastCompletedAt': _now_iso(),
    })

    emit_activity(pid, 'QUESTIONNAIRE_COMPLETED',
                  f"Completed {d.get('shortName', payload.measureId)} questionnaire", 'client')
    # Return OutcomeResponse shape (not canonical) to match what the patient frontend expects
    return ok({
        'id': doc_id,
        'measureId': payload.measureId,
        'weekOf': payload.weekOf,
        'responses': payload.responses,
        'score': payload.score,
        'completedAt': response_data['completedAt'],
    }, status=201)


# ── P14 startInterventionSession ───────────────────────────────────

@require_role('patient')
def start_intervention_session():
    pid, e = _patient_or_403()
    if e:
        return e
    try:
        payload = InterventionSessionStart.model_validate(request.get_json(silent=True) or {})
    except ValidationError as ve:
        return err(f'Invalid body: {ve.errors()}', 400)
    defn = db().collection('interventions').document(payload.interventionId).get()
    duration = (defn.to_dict() or {}).get('durationSeconds', 120) if defn.exists else 120
    data = {
        'interventionId': payload.interventionId,
        'startedAt': _now_iso(),
        'durationSeconds': duration,
    }
    ref = db().collection('patients').document(pid).collection('interventionSessions').document()
    ref.set(data)
    return ok({'id': ref.id, **data}, status=201)


# ── list intervention sessions (for progress aggregation) ──────────

@require_role('patient')
def list_intervention_sessions():
    pid, e = _patient_or_403()
    if e:
        return e
    docs = db().collection('patients').document(pid).collection('interventionSessions') \
        .order_by('startedAt', direction='DESCENDING').limit(100).stream()
    return ok([{'id': d.id, **(d.to_dict() or {})} for d in docs])


# ── dashboard (aggregator for ClientHome) ──────────────────────────

@require_role('patient')
def dashboard():
    """Single endpoint returning combined ClientPortalOverview-equivalent for the patient.

    Used by ClientHome to reduce round trips on initial load.
    """
    pid, e = _patient_or_403()
    if e:
        return e
    base = db().collection('patients').document(pid)
    homework = [{'id': d.id, **(d.to_dict() or {})} for d in base.collection('homework').stream()]
    journal_count = len(list(base.collection('journal').stream()))
    return ok({
        'patientId': pid,
        'homework': homework,
        'journalCount': journal_count,
    })
