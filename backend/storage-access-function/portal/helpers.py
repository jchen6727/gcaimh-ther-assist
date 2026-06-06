"""
Cross-cutting helpers: activity events, document translations, pagination.
"""
import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from firebase_admin import firestore
from flask import request, jsonify

# ── Firestore client (lazy) ─────────────────────────────────────────

_db = None


def db():
    global _db
    if _db is None:
        _db = firestore.client()
    return _db


def server_ts():
    return firestore.SERVER_TIMESTAMP


# ── Response helpers ────────────────────────────────────────────────

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
}


def ok(payload: Any, status: int = 200) -> Tuple:
    return (jsonify(payload), status, CORS_HEADERS)


def err(message: str, status: int) -> Tuple:
    return (jsonify({'error': message}), status, CORS_HEADERS)


# ── Activity events ─────────────────────────────────────────────────

def emit_activity(patient_id: str, event_type: str, description: str, actor: str) -> None:
    """Append an ActivityEvent to /patients/{patient_id}/activity.

    Called from inside mutation handlers AFTER the primary write succeeds.
    Failures are logged but do not propagate (activity log is best-effort).
    """
    try:
        db().collection('patients').document(patient_id).collection('activity').add({
            'type': event_type,
            'description': description,
            'actor': actor,
            'timestamp': server_ts(),
        })
    except Exception as e:
        logging.warning(f"[portal] Failed to emit activity event {event_type} for patient {patient_id}: {e}")


# ── Pagination ──────────────────────────────────────────────────────

def parse_pagination() -> Tuple[Optional[str], int]:
    """Extract ?after=... and ?limit=... from request query string.

    Returns (after_doc_id, limit). Limit clamped to [1, 200], default 50.
    """
    after = request.args.get('after') or None
    try:
        limit = int(request.args.get('limit', 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))
    return after, limit


def apply_pagination(query, collection_ref, order_field: str, order_dir: str, after: Optional[str], limit: int):
    """Apply cursor-based pagination to a Firestore query.

    The cursor (`after`) is the document ID to start AFTER. We fetch that doc to get its
    `order_field` value, then use start_after().
    """
    query = query.order_by(order_field, direction=order_dir).limit(limit)
    if after:
        try:
            anchor = collection_ref.document(after).get()
            if anchor.exists:
                query = query.start_after(anchor)
        except Exception as e:
            logging.warning(f"[portal] Pagination cursor invalid: {after} ({e})")
    return query


# ── Document translations ───────────────────────────────────────────

def session_doc_to_therapy_session(doc) -> Dict[str, Any]:
    """Translate existing /sessions/{id} document → patient-facing TherapySession.

    The existing schema stores PHI fields that should be stripped before sending to patients.
    Uses the same redaction logic as therapy-analysis-function's get_patient_summary action.
    """
    data = doc.to_dict() or {}
    full = data.get('full_summary') or {}

    # Strip PHI fields the patient should not see (risk_assessment, techniques_used, key_moments,
    # manual_reference on homework). Mirror of therapy-analysis-function/main.py get_patient_summary.
    homework_safe = [
        {'task': hw.get('task', ''), 'rationale': hw.get('rationale', '')}
        for hw in full.get('homework_assignments', []) or []
    ]

    return {
        'id': doc.id,
        'date': data.get('date', ''),
        'durationMinutes': int(data.get('duration_minutes') or 0),
        'summary': data.get('summary_text', ''),
        'themes': full.get('themes', []) or [],
        'keyMoments': full.get('key_moments', []) or [],   # therapist-only — see note below
        'techniques': full.get('techniques_used', []) or [],
        'homework': [hw.get('task', '') for hw in homework_safe],
        'insights': full.get('insights', []) or [],
        'emotionalState': full.get('emotional_state'),
    }


def session_doc_to_therapy_session_patient_view(doc) -> Dict[str, Any]:
    """Same as session_doc_to_therapy_session but redacts therapist-only fields.

    Used when serving /portal/me/sessions to a patient.
    """
    result = session_doc_to_therapy_session(doc)
    # Patient should not see internal therapist review fields.
    result.pop('keyMoments', None)
    result.pop('techniques', None)
    return result


def patient_doc_to_bridge_client(doc) -> Dict[str, Any]:
    """Project /patients/{id} into BridgeClient shape for the therapist portal."""
    data = doc.to_dict() or {}
    return {
        'id': doc.id,
        'name': data.get('name', ''),
        'status': data.get('status', 'active'),
        'primaryConcern': data.get('primaryConcern') or data.get('primary_concern'),
        'age': data.get('age'),
    }


def questionnaire_def_doc_to_outcome_measure(doc) -> Dict[str, Any]:
    """Canonical QuestionnaireDefinition (with items[]) → patient-facing OutcomeMeasure."""
    d = doc.to_dict() or {}
    return {
        'id': doc.id,
        'name': d.get('name', ''),
        'shortName': d.get('shortName', ''),
        'description': d.get('description', ''),
        'category': d.get('category', 'GENERAL'),
        'items': d.get('items', []),
        'maxScore': d.get('maxScore', 0),
        'scoring': d.get('scoring', 'sum'),
        'thresholds': d.get('thresholds', []),
        'cadence': d.get('cadence', 'weekly'),
    }


def questionnaire_def_doc_to_definition(doc) -> Dict[str, Any]:
    """Canonical QuestionnaireDefinition → therapist-facing definition (no items[])."""
    d = doc.to_dict() or {}
    items = d.get('items', []) or []
    return {
        'id': doc.id,
        'name': d.get('name', ''),
        'shortName': d.get('shortName', ''),
        'description': d.get('description', ''),
        'itemCount': len(items),
        'maxScore': d.get('maxScore', 0),
        'estimatedMinutes': d.get('estimatedMinutes', 5),
        'category': d.get('category', 'GENERAL'),
        'thresholds': d.get('thresholds', []),
    }


def response_doc_to_outcome_response(doc) -> Dict[str, Any]:
    """Canonical QuestionnaireResponse → patient-facing OutcomeResponse.

    Canonical stores items: [{itemIndex, value}]. Patient frontend wants responses: number[]
    in original item order.
    """
    d = doc.to_dict() or {}
    items = d.get('items', []) or []
    # Sort by itemIndex to preserve question order, then extract value
    items_sorted = sorted(items, key=lambda x: x.get('itemIndex', 0))
    responses = [int(item.get('value', 0)) for item in items_sorted]
    return {
        'id': doc.id,
        'measureId': d.get('questionnaireId', ''),
        'weekOf': d.get('weekOf', ''),
        'responses': responses,
        'score': d.get('totalScore', 0),
        'completedAt': d.get('completedAt', ''),
    }
