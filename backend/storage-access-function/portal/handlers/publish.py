"""
Therapist publish-draft endpoints.

Drafts are created by the LLM (therapy-analysis-function writes to
/patients/{id}/publishDrafts/{draftId} directly after a session summary).
This module provides only read/update/publish/unpublish.

  T10 GET    /portal/clients/{id}/publish-draft                read most recent (or null)
  T11 PATCH  /portal/clients/{id}/publish-draft/{draftId}      update sections (visibility toggles)
  T12 POST   /portal/clients/{id}/publish-draft/{draftId}/publish
  T13 POST   /portal/clients/{id}/publish-draft/{draftId}/unpublish
"""
from datetime import datetime, timezone
from flask import request
from pydantic import ValidationError
from ..auth import require_role, require_owns_patient
from ..helpers import db, ok, err, emit_activity
from ..models import PublishDraftPatch


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coll(patient_id: str):
    return db().collection('patients').document(patient_id).collection('publishDrafts')


@require_role('therapist')
@require_owns_patient
def get_draft(patient_id: str):
    """Returns the most recently-created draft, or null if none."""
    docs = _coll(patient_id).order_by('sessionDate', direction='DESCENDING').limit(1).stream()
    docs = list(docs)
    if not docs:
        return ok(None)
    d = docs[0]
    return ok({'id': d.id, 'clientId': patient_id, **(d.to_dict() or {})})


@require_role('therapist')
@require_owns_patient
def update_draft(patient_id: str, draft_id: str):
    try:
        payload = PublishDraftPatch.model_validate(request.get_json(silent=True) or {})
    except ValidationError as e:
        return err(f'Invalid body: {e.errors()}', 400)

    ref = _coll(patient_id).document(draft_id)
    if not ref.get().exists:
        return err('Draft not found', 404)
    ref.update({'sections': payload.sections.model_dump()})
    updated = ref.get()
    return ok({'id': updated.id, 'clientId': patient_id, **(updated.to_dict() or {})})


@require_role('therapist')
@require_owns_patient
def publish_draft(patient_id: str, draft_id: str):
    ref = _coll(patient_id).document(draft_id)
    if not ref.get().exists:
        return err('Draft not found', 404)
    ref.update({'published': True, 'publishedAt': _now_iso()})
    emit_activity(patient_id, 'SUMMARY_PUBLISHED',
                  f"Session summary published to client", 'therapist')
    return ok({'success': True})


@require_role('therapist')
@require_owns_patient
def unpublish_draft(patient_id: str, draft_id: str):
    ref = _coll(patient_id).document(draft_id)
    if not ref.get().exists:
        return err('Draft not found', 404)
    ref.update({'published': False, 'publishedAt': None})
    emit_activity(patient_id, 'SUMMARY_UNPUBLISHED',
                  f"Session summary unpublished", 'therapist')
    return ok({'success': True})
