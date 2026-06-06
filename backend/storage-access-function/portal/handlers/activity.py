"""
Activity log endpoints.

  T14 GET  /portal/clients/{id}/activity          paginated
  T15 POST /portal/clients/{id}/activity          manual entry by therapist
"""
from flask import request
from pydantic import ValidationError
from ..auth import require_role, require_owns_patient
from ..helpers import db, ok, err, server_ts, parse_pagination
from ..models import ActivityEventCreate


def _coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('activity')


@require_role('therapist')
@require_owns_patient
def list_activity(patient_id: str):
    after, limit = parse_pagination()
    coll = _coll(patient_id)
    query = coll.order_by('timestamp', direction='DESCENDING').limit(limit)
    if after:
        anchor = coll.document(after).get()
        if anchor.exists:
            query = query.start_after(anchor)
    events = []
    for d in query.stream():
        data = d.to_dict() or {}
        ts = data.get('timestamp')
        events.append({
            'id': d.id,
            'clientId': patient_id,
            'type': data.get('type'),
            'description': data.get('description', ''),
            'actor': data.get('actor', 'therapist'),
            'timestamp': ts.isoformat() if ts and hasattr(ts, 'isoformat') else ts,
        })
    return ok(events)


@require_role('therapist')
@require_owns_patient
def add_activity(patient_id: str):
    try:
        payload = ActivityEventCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    data = {**payload.model_dump(), 'timestamp': server_ts()}
    ref = _coll(patient_id).add(data)
    new_id = ref[1].id
    return ok({'id': new_id, 'clientId': patient_id, **payload.model_dump()}, status=201)
