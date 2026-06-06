"""
Therapist questionnaire endpoints.

  T19 GET    /portal/clients/{id}/questionnaires
  T20 POST   /portal/clients/{id}/questionnaires                 assign
  T21 PATCH  /portal/clients/{id}/questionnaires/{aId}/status    pause / remove
  T22 GET    /portal/clients/{id}/questionnaires/{aId}/responses
"""
from datetime import datetime, timezone
from flask import request
from pydantic import ValidationError
from ..auth import require_role, require_owns_patient
from ..helpers import db, ok, err, emit_activity, parse_pagination
from ..models import QuestionnaireAssign, QuestionnaireStatusUpdate


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assignments_coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('questionnaireAssignments')


def _responses_coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('questionnaireResponses')


def _resolve_definition(qid: str):
    doc = db().collection('questionnaireDefinitions').document(qid).get()
    return doc if doc.exists else None


@require_role('therapist')
@require_owns_patient
def list_assignments(patient_id: str):
    docs = _assignments_coll(patient_id).stream()
    return ok([{'id': d.id, 'clientId': patient_id, **(d.to_dict() or {})} for d in docs])


@require_role('therapist')
@require_owns_patient
def assign_questionnaire(patient_id: str):
    try:
        payload = QuestionnaireAssign.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    defn = _resolve_definition(payload.questionnaireId)
    if not defn:
        return err(f'Questionnaire definition not found: {payload.questionnaireId}', 404)
    d = defn.to_dict() or {}

    data = {
        'clientId': patient_id,
        'questionnaireId': payload.questionnaireId,
        'questionnaireName': d.get('name', ''),
        'questionnaireShortName': d.get('shortName', ''),
        'cadence': payload.cadence,
        'status': 'ACTIVE',
        'assignedAt': _now_iso(),
        'note': payload.note,
        'completionCount': 0,
    }
    ref = _assignments_coll(patient_id).document()
    ref.set({k: v for k, v in data.items() if v is not None})
    emit_activity(patient_id, 'QUESTIONNAIRE_ASSIGNED',
                  f"Assigned {d.get('shortName', payload.questionnaireId)} questionnaire ({payload.cadence.lower()})",
                  'therapist')
    return ok({'id': ref.id, **{k: v for k, v in data.items() if v is not None}}, status=201)


@require_role('therapist')
@require_owns_patient
def update_assignment_status(patient_id: str, assignment_id: str):
    try:
        payload = QuestionnaireStatusUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    ref = _assignments_coll(patient_id).document(assignment_id)
    snap = ref.get()
    if not snap.exists:
        return err('Assignment not found', 404)

    update = {'status': payload.status}
    if payload.status == 'PAUSED':
        update['pausedAt'] = _now_iso()
    elif payload.status == 'REMOVED':
        update['removedAt'] = _now_iso()
    ref.update(update)

    label = (snap.to_dict() or {}).get('questionnaireShortName', assignment_id)
    event_map = {
        'PAUSED': 'QUESTIONNAIRE_PAUSED',
        'REMOVED': 'QUESTIONNAIRE_REMOVED',
    }
    if payload.status in event_map:
        emit_activity(patient_id, event_map[payload.status],
                      f"Questionnaire {label} {payload.status.lower()}", 'therapist')
    return ok({'success': True})


@require_role('therapist')
@require_owns_patient
def list_responses(patient_id: str, assignment_id: str):
    after, limit = parse_pagination()
    coll = _responses_coll(patient_id)
    query = coll.where('assignmentId', '==', assignment_id) \
        .order_by('weekOf', direction='DESCENDING').limit(limit)
    if after:
        anchor = coll.document(after).get()
        if anchor.exists:
            query = query.start_after(anchor)
    return ok([{'id': d.id, 'clientId': patient_id, **(d.to_dict() or {})} for d in query.stream()])
