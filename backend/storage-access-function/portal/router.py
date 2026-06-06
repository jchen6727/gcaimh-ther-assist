"""
Portal request router.

Dispatches /portal/* requests to the appropriate handler based on path + method.

Routes use simple path-pattern matching rather than Flask Blueprints since the function
is invoked as a single functions_framework HTTP entry point.
"""
import re
from typing import Tuple, Callable, Optional
from flask import request
from .helpers import err, CORS_HEADERS
from .handlers import (
    clients, homework, interventions, publish, activity,
    catalog, questionnaires, journal, sessions, me,
)


# Each route: (method, pattern, handler)
# Pattern uses {name} for path params extracted into kwargs.
_ROUTES = [
    # ── Therapist: clients ─────────────────────────────────────────
    ('GET', r'^/portal/clients$', clients.list_clients),
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/overview$', clients.get_overview),
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/progress$', clients.get_progress),
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/integrative-analysis$', clients.get_integrative_analysis),

    # ── Therapist: homework ────────────────────────────────────────
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/homework$', homework.list_homework),
    ('POST', r'^/portal/clients/(?P<patient_id>[^/]+)/homework$', homework.upsert_homework),
    ('PATCH', r'^/portal/clients/(?P<patient_id>[^/]+)/homework/(?P<hw_id>[^/]+)/status$', homework.update_status),
    ('PATCH', r'^/portal/clients/(?P<patient_id>[^/]+)/homework/(?P<hw_id>[^/]+)$', homework.patch_homework),

    # ── Therapist: interventions ───────────────────────────────────
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/interventions$', interventions.list_interventions),
    ('POST', r'^/portal/clients/(?P<patient_id>[^/]+)/interventions$', interventions.assign_intervention),
    ('DELETE', r'^/portal/clients/(?P<patient_id>[^/]+)/interventions/(?P<assignment_id>[^/]+)$', interventions.archive_intervention),

    # ── Therapist: publish drafts ──────────────────────────────────
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/publish-draft$', publish.get_draft),
    ('PATCH', r'^/portal/clients/(?P<patient_id>[^/]+)/publish-draft/(?P<draft_id>[^/]+)$', publish.update_draft),
    ('POST', r'^/portal/clients/(?P<patient_id>[^/]+)/publish-draft/(?P<draft_id>[^/]+)/publish$', publish.publish_draft),
    ('POST', r'^/portal/clients/(?P<patient_id>[^/]+)/publish-draft/(?P<draft_id>[^/]+)/unpublish$', publish.unpublish_draft),

    # ── Therapist: activity ────────────────────────────────────────
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/activity$', activity.list_activity),
    ('POST', r'^/portal/clients/(?P<patient_id>[^/]+)/activity$', activity.add_activity),

    # ── Therapist: questionnaires ──────────────────────────────────
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/questionnaires$', questionnaires.list_assignments),
    ('POST', r'^/portal/clients/(?P<patient_id>[^/]+)/questionnaires$', questionnaires.assign_questionnaire),
    ('PATCH', r'^/portal/clients/(?P<patient_id>[^/]+)/questionnaires/(?P<assignment_id>[^/]+)/status$', questionnaires.update_assignment_status),
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/questionnaires/(?P<assignment_id>[^/]+)/responses$', questionnaires.list_responses),

    # ── Therapist: sessions ────────────────────────────────────────
    ('GET', r'^/portal/clients/(?P<patient_id>[^/]+)/sessions$', sessions.list_sessions_therapist),

    # ── Catalog ────────────────────────────────────────────────────
    ('GET', r'^/portal/catalog/modules$', catalog.list_modules),
    ('GET', r'^/portal/catalog/interventions$', catalog.list_interventions),
    ('GET', r'^/portal/catalog/questionnaires$', catalog.list_questionnaires),

    # ── Patient self-service (/me/*) ───────────────────────────────
    ('GET', r'^/portal/me/dashboard$', me.dashboard),
    ('GET', r'^/portal/me/progress$', me.progress),
    ('GET', r'^/portal/me/homework$', me.list_homework),
    ('PATCH', r'^/portal/me/homework/(?P<hw_id>[^/]+)/status$', me.update_homework_status),
    ('GET', r'^/portal/me/interventions$', me.list_interventions),
    ('GET', r'^/portal/me/intervention-sessions$', me.list_intervention_sessions),
    ('POST', r'^/portal/me/intervention-sessions$', me.start_intervention_session),
    ('GET', r'^/portal/me/journal$', me.list_journal),
    ('POST', r'^/portal/me/journal$', me.upsert_journal),
    ('GET', r'^/portal/me/integrative-analysis$', me.integrative_analysis),
    ('GET', r'^/portal/me/sessions$', me.list_sessions),
    ('GET', r'^/portal/me/outcome-measures$', me.list_outcome_measures),
    ('GET', r'^/portal/me/outcome-schedule$', me.outcome_schedule),
    ('GET', r'^/portal/me/outcome-responses$', me.list_outcome_responses),
    ('POST', r'^/portal/me/outcome-responses$', me.submit_outcome_response),
]


def handle_portal_request(path: str) -> Tuple:
    """Dispatch the incoming request to the matching handler.

    `path` is the URL path starting with `/portal/...`.
    Returns Flask response tuple (body, status, headers).
    """
    # CORS preflight
    if request.method == 'OPTIONS':
        return ('', 204, CORS_HEADERS)

    method = request.method.upper()

    for route_method, pattern, handler in _ROUTES:
        if route_method != method:
            continue
        match = re.match(pattern, path)
        if match:
            return handler(**match.groupdict())

    return err(f'Portal route not found: {method} {path}', 404)
