"""
Therapist homework endpoints.

  T3 GET    /portal/clients/{id}/homework
  T4 POST   /portal/clients/{id}/homework
  T5 PATCH  /portal/clients/{id}/homework/{hwId}/status
  T6 PATCH  /portal/clients/{id}/homework/{hwId}             (reschedule/note)
"""
from datetime import datetime, timezone
from flask import request, g
from pydantic import ValidationError
from ..auth import require_role, require_owns_patient
from ..helpers import db, ok, err, emit_activity, server_ts
from ..models import HomeworkUpsert, HomeworkStatusUpdate, HomeworkPatch


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _homework_coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('homework')


@require_role('therapist')
@require_owns_patient
def list_homework(patient_id: str):
    docs = _homework_coll(patient_id).stream()
    return ok([{'id': d.id, 'clientId': patient_id, **(d.to_dict() or {})} for d in docs])


@require_role('therapist')
@require_owns_patient
def upsert_homework(patient_id: str):
    try:
        payload = HomeworkUpsert.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    data = payload.model_dump(exclude_none=True)
    data['clientId'] = patient_id
    data['assignedAt'] = _now_iso()

    ref = _homework_coll(patient_id).document()
    ref.set(data)
    emit_activity(patient_id, 'HOMEWORK_ASSIGNED',
                  f"Assigned homework: {payload.moduleTitle}", 'therapist')
    return ok({'id': ref.id, **data}, status=201)


@require_role('therapist')
@require_owns_patient
def update_status(patient_id: str, hw_id: str):
    try:
        payload = HomeworkStatusUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    ref = _homework_coll(patient_id).document(hw_id)
    snap = ref.get()
    if not snap.exists:
        return err('Homework not found', 404)

    ref.update({'status': payload.status})
    title = (snap.to_dict() or {}).get('moduleTitle', hw_id)
    event_map = {
        'COMPLETED': 'HOMEWORK_COMPLETED',
        'ARCHIVED': 'HOMEWORK_ARCHIVED',
    }
    if payload.status in event_map:
        emit_activity(patient_id, event_map[payload.status],
                      f"Homework status: {title} → {payload.status.lower()}", 'therapist')
    return ok({'success': True})


@require_role('therapist')
@require_owns_patient
def patch_homework(patient_id: str, hw_id: str):
    """General update — supports reschedule (dueAt) and note edits.

    Emits HOMEWORK_RESCHEDULED if dueAt changes.
    """
    try:
        payload = HomeworkPatch.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    update = payload.model_dump(exclude_none=True)
    if not update:
        return err('Empty patch', 400)

    ref = _homework_coll(patient_id).document(hw_id)
    snap = ref.get()
    if not snap.exists:
        return err('Homework not found', 404)

    old = snap.to_dict() or {}
    ref.update(update)
    if 'dueAt' in update and update['dueAt'] != old.get('dueAt'):
        emit_activity(patient_id, 'HOMEWORK_RESCHEDULED',
                      f"Homework rescheduled: {old.get('moduleTitle', hw_id)}", 'therapist')
    return ok({'success': True})
