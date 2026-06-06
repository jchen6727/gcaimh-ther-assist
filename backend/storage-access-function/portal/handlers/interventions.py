"""
Therapist intervention assignment endpoints.

  T7 GET    /portal/clients/{id}/interventions
  T8 POST   /portal/clients/{id}/interventions
  T9 DELETE /portal/clients/{id}/interventions/{aId}   (soft delete → status=ARCHIVED)
"""
from datetime import datetime, timezone
from flask import request
from pydantic import ValidationError
from ..auth import require_role, require_owns_patient
from ..helpers import db, ok, err, emit_activity
from ..models import InterventionUpsert


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('interventionAssignments')


@require_role('therapist')
@require_owns_patient
def list_interventions(patient_id: str):
    docs = _coll(patient_id).stream()
    return ok([{'id': d.id, 'clientId': patient_id, **(d.to_dict() or {})} for d in docs])


@require_role('therapist')
@require_owns_patient
def assign_intervention(patient_id: str):
    try:
        payload = InterventionUpsert.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    data = payload.model_dump(exclude_none=True)
    data['clientId'] = patient_id
    data['assignedAt'] = _now_iso()

    ref = _coll(patient_id).document()
    ref.set(data)
    emit_activity(patient_id, 'INTERVENTION_ASSIGNED',
                  f"Assigned intervention: {payload.interventionTitle}", 'therapist')
    return ok({'id': ref.id, **data}, status=201)


@require_role('therapist')
@require_owns_patient
def archive_intervention(patient_id: str, assignment_id: str):
    """Soft-delete: status = ARCHIVED."""
    ref = _coll(patient_id).document(assignment_id)
    snap = ref.get()
    if not snap.exists:
        return err('Intervention assignment not found', 404)
    ref.update({'status': 'ARCHIVED'})
    title = (snap.to_dict() or {}).get('interventionTitle', assignment_id)
    emit_activity(patient_id, 'INTERVENTION_ARCHIVED',
                  f"Archived intervention: {title}", 'therapist')
    return ok({'success': True})
