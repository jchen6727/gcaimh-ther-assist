"""
Journal helpers used by /me/journal endpoints (and exposed to patient via me.py).
"""
from datetime import datetime, timezone
from typing import Optional
from ..helpers import db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def journal_coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('journal')


def list_entries(patient_id: str, after: Optional[str], limit: int) -> list:
    coll = journal_coll(patient_id)
    query = coll.order_by('date', direction='DESCENDING').limit(limit)
    if after:
        anchor = coll.document(after).get()
        if anchor.exists:
            query = query.start_after(anchor)
    return [{'id': d.id, **(d.to_dict() or {})} for d in query.stream()]


def upsert_entry(patient_id: str, payload: dict) -> dict:
    now = _now_iso()
    coll = journal_coll(patient_id)
    eid = payload.get('id')
    if eid:
        ref = coll.document(eid)
        snap = ref.get()
        if snap.exists:
            data = {**(snap.to_dict() or {}), **{k: v for k, v in payload.items() if k != 'id'}, 'updatedAt': now}
            ref.update({k: v for k, v in payload.items() if k != 'id'} | {'updatedAt': now})
            return {'id': eid, **data}
    # create
    data = {
        'date': payload.get('date') or now[:10],
        'moduleId': payload.get('moduleId'),
        'interventionId': payload.get('interventionId'),
        'sessionId': payload.get('sessionId'),
        'keyInsights': payload.get('keyInsights', ''),
        'personalApplication': payload.get('personalApplication', ''),
        'discussionTopics': payload.get('discussionTopics', ''),
        'createdAt': now,
        'updatedAt': now,
    }
    data = {k: v for k, v in data.items() if v is not None}
    ref = coll.document()
    ref.set(data)
    return {'id': ref.id, **data}
