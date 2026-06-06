"""
Catalog endpoints — read-only content library.

Any authenticated user (therapist or patient) may read.
Seeded one-time from setup_services/seed_catalog/.

Endpoints:
  GET /portal/catalog/modules           T16 + P1
  GET /portal/catalog/interventions     T17 + P3
  GET /portal/catalog/questionnaires    T18
"""
from functools import wraps
from flask import request
from firebase_admin import auth as firebase_auth
from ..helpers import db, ok, err, questionnaire_def_doc_to_definition


def _require_authenticated(handler):
    """Lightweight auth — any valid Firebase token, no role check."""
    @wraps(handler)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return err('Authentication required', 401)
        try:
            firebase_auth.verify_id_token(auth_header.split(' ', 1)[1])
        except Exception:
            return err('Invalid token', 401)
        return handler(*args, **kwargs)
    return wrapped


@_require_authenticated
def list_modules():
    docs = db().collection('modules').stream()
    modules = []
    for doc in docs:
        d = doc.to_dict() or {}
        modules.append({
            'id': doc.id,
            'title': d.get('title', ''),
            'category': d.get('category', ''),
            'estimatedMinutes': d.get('estimatedMinutes', 0),
            'summary': d.get('summary', ''),
            'tags': d.get('tags', []),
        })
    return ok(modules)


@_require_authenticated
def list_interventions():
    docs = db().collection('interventions').stream()
    interventions = []
    for doc in docs:
        d = doc.to_dict() or {}
        interventions.append({
            'id': doc.id,
            'title': d.get('title', ''),
            'type': d.get('type', ''),
            'durationSeconds': d.get('durationSeconds'),
            'description': d.get('description', ''),
        })
    return ok(interventions)


@_require_authenticated
def list_questionnaires():
    """Therapist-facing list — omits items[] (use /portal/me/outcome-measures for full)."""
    docs = db().collection('questionnaireDefinitions').stream()
    return ok([questionnaire_def_doc_to_definition(doc) for doc in docs])
