"""
Therapy session endpoints — reads existing top-level /sessions collection (not subcollection).

  T20 GET /portal/clients/{id}/sessions    therapist view (full TherapySession shape)

Patient-side reads (/portal/me/sessions) live in me.py and use the same query but with
patient-safe PHI redaction.
"""
from ..auth import require_role, require_owns_patient
from ..helpers import db, ok, parse_pagination, session_doc_to_therapy_session


@require_role('therapist')
@require_owns_patient
def list_sessions_therapist(patient_id: str):
    after, limit = parse_pagination()
    coll = db().collection('sessions')
    query = coll.where('patient_id', '==', patient_id).order_by('date', direction='DESCENDING').limit(limit)
    if after:
        anchor = coll.document(after).get()
        if anchor.exists:
            query = query.start_after(anchor)
    return ok([session_doc_to_therapy_session(d) for d in query.stream()])
