"""
Portal authentication and authorization.

Provides:
- verify_token(): extracts and validates Firebase ID token
- load_user(): reads /users/{uid} from Firestore
- @require_role('therapist'|'patient'): role-gated endpoint
- @require_owns_patient: therapist must own the patient in URL path

DEV-MODE BYPASS:
  When PORTAL_DEV_AUTH_BYPASS env var == 'true', tokens starting with 'dev-'
  are accepted without Firebase verification and decoded by convention:
    dev-therapist-<email>  → { uid: 'dev-<email>', email, role: 'therapist' }
    dev-patient-<email>    → { uid: 'dev-<email>', email, role: 'patient' }
  NEVER set this env var in production deployments.
"""
import os
import logging
from functools import wraps
from typing import Optional, Dict, Any, Callable
from flask import request, g, jsonify
from firebase_admin import auth as firebase_auth, firestore

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = firestore.client()
    return _db


def _dev_bypass_enabled() -> bool:
    return os.environ.get('PORTAL_DEV_AUTH_BYPASS', '').strip().lower() == 'true'


def _decode_dev_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a dev-mode token of the form 'dev-<role>-<email>'.

    Returns synthesized claims dict, or None if the token doesn't parse.
    """
    if not token.startswith('dev-'):
        return None
    parts = token.split('-', 2)
    if len(parts) != 3:
        return None
    _, role, email = parts
    if role not in ('therapist', 'patient'):
        return None
    if not email or '@' not in email:
        return None
    return {
        'uid': f'dev-{email}',
        'email': email,
        'role': role,
    }


def verify_token() -> Optional[Dict[str, Any]]:
    """Verify Bearer token in Authorization header, return decoded claims or None.

    Accepts dev-mode tokens when PORTAL_DEV_AUTH_BYPASS is enabled.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ', 1)[1]

    # Dev-mode bypass
    if _dev_bypass_enabled():
        dev_claims = _decode_dev_token(token)
        if dev_claims:
            logging.warning(f"[portal-auth] DEV BYPASS in use for {dev_claims['email']} (role={dev_claims['role']})")
            return dev_claims

    try:
        return firebase_auth.verify_id_token(token)
    except Exception as e:
        logging.warning(f"[portal-auth] Token verification failed: {e}")
        return None


def load_user(uid: str) -> Optional[Dict[str, Any]]:
    """Read /users/{uid} from Firestore. Returns None if not found.

    In dev-bypass mode for dev-* UIDs, fall back to env-configured dev user
    so endpoints work without needing a real /users doc.
    """
    try:
        doc = _get_db().collection('users').document(uid).get()
        if doc.exists:
            data = doc.to_dict()
            data['uid'] = uid
            return data
    except Exception as e:
        logging.error(f"[portal-auth] Failed to load /users/{uid}: {e}")

    # Dev-mode fallback: synthesize a user record for dev-* UIDs
    if _dev_bypass_enabled() and uid.startswith('dev-'):
        # PORTAL_DEV_PATIENT_IDS: comma-separated patient IDs that the dev therapist manages
        dev_patient_ids = [p.strip() for p in os.environ.get('PORTAL_DEV_PATIENT_IDS', '').split(',') if p.strip()]
        # PORTAL_DEV_PATIENT_ID: which patient the dev patient user IS
        dev_self_patient_id = os.environ.get('PORTAL_DEV_PATIENT_ID', '').strip() or None
        return {
            'uid': uid,
            'email': uid.replace('dev-', ''),
            'managedPatientIds': dev_patient_ids,
            'patientId': dev_self_patient_id,
        }

    return None


def _error(message: str, status: int) -> tuple:
    """Standard error response (matches existing storage_access format)."""
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }
    return (jsonify({'error': message}), status, headers)


def require_role(role: str) -> Callable:
    """Decorator: endpoint requires the user's role to match `role`.

    On success: sets g.user (decoded token + Firestore user doc merged).
    On failure: returns 401 (no token) or 403 (wrong role).
    """
    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        def wrapped(*args, **kwargs):
            decoded = verify_token()
            if not decoded:
                return _error('Authentication required', 401)

            uid = decoded.get('uid')
            user_doc = load_user(uid)
            if not user_doc:
                return _error('User profile not found', 403)

            # Role can come from custom claims (preferred, fast) or Firestore doc (fallback)
            user_role = decoded.get('role') or user_doc.get('role')
            if user_role != role:
                logging.warning(
                    f"[portal-auth] Role mismatch: {decoded.get('email')} has '{user_role}', needs '{role}'"
                )
                return _error('Forbidden: role mismatch', 403)

            g.user = {**user_doc, **decoded, 'role': user_role}
            return handler(*args, **kwargs)
        return wrapped
    return decorator


def require_owns_patient(handler: Callable) -> Callable:
    """Decorator: therapist must own the patient_id in URL path.

    Must be used AFTER @require_role('therapist'). Looks at kwargs['patient_id'].
    """
    @wraps(handler)
    def wrapped(*args, **kwargs):
        patient_id = kwargs.get('patient_id')
        if not patient_id:
            return _error('Missing patient_id', 400)

        managed = g.user.get('managedPatientIds', []) or []
        if patient_id not in managed:
            logging.warning(
                f"[portal-auth] Therapist {g.user.get('email')} does not manage patient {patient_id}"
            )
            return _error('Forbidden: not your patient', 403)
        return handler(*args, **kwargs)
    return wrapped


def derive_self_patient_id() -> Optional[str]:
    """For /me/* endpoints, get the patient_id from g.user (set by require_role('patient'))."""
    return g.user.get('patientId') if hasattr(g, 'user') else None
