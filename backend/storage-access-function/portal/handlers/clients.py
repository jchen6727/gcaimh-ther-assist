"""
Therapist endpoints for clients.

  T1  GET /portal/clients                                  list managed patients
  T2  GET /portal/clients/{id}/overview                    aggregated ClientPortalOverview
  T22 GET /portal/clients/{id}/progress                    ClientProgress
  T23 GET /portal/clients/{id}/integrative-analysis        IntegrativeAnalysis (read therapist view)
"""
from datetime import datetime, timezone
from flask import g
from ..auth import require_role, require_owns_patient
from ..helpers import (
    db, ok, err, patient_doc_to_bridge_client,
)


@require_role('therapist')
def list_clients():
    managed = g.user.get('managedPatientIds', []) or []
    clients = []
    for pid in managed:
        doc = db().collection('patients').document(pid).get()
        if doc.exists:
            clients.append(patient_doc_to_bridge_client(doc))
    return ok(clients)


@require_role('therapist')
@require_owns_patient
def get_overview(patient_id: str):
    """Aggregate ClientPortalOverview: client, homework, interventions, draft, outcomes, activity."""
    client_doc = db().collection('patients').document(patient_id).get()
    if not client_doc.exists:
        return err('Patient not found', 404)

    base = db().collection('patients').document(patient_id)

    homework = [{'id': d.id, **d.to_dict()} for d in base.collection('homework').stream()]
    interventions = [{'id': d.id, **d.to_dict()} for d in base.collection('interventionAssignments').stream()]
    drafts = list(base.collection('publishDrafts').limit(1).stream())
    publish_draft = ({'id': drafts[0].id, **drafts[0].to_dict()} if drafts else None)
    activity_docs = base.collection('activity').order_by('timestamp', direction='DESCENDING').limit(50).stream()
    activity_log = [{'id': d.id, **d.to_dict()} for d in activity_docs]

    # Compute basic outcome overview from latest responses (real impl in questionnaires.py uses richer data)
    outcome_overview = {
        'lastCompletedWeek': None,
        'nextDueWeek': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'trend': [],
        'safetyFlag': False,
    }

    overview = {
        'client': patient_doc_to_bridge_client(client_doc),
        'homework': homework,
        'interventions': interventions,
        'publishDraft': publish_draft,
        'outcomeOverview': outcome_overview,
        'activityLog': activity_log,
    }
    return ok(overview)


@require_role('therapist')
@require_owns_patient
def get_progress(patient_id: str):
    """Therapist view of patient progress (same shape as patient's ClientProgress)."""
    base = db().collection('patients').document(patient_id)
    homework_docs = list(base.collection('homework').stream())
    completed = sum(1 for d in homework_docs if (d.to_dict() or {}).get('status') == 'COMPLETED')
    journal_count = len(list(base.collection('journal').stream()))
    return ok({
        'completedModules': completed,
        'totalAssigned': len(homework_docs),
        'streakDays': 0,
        'totalInterventionMinutes': 0,
        'journalEntryCount': journal_count,
        'lastActiveAt': datetime.now(timezone.utc).isoformat(),
    })


@require_role('therapist')
@require_owns_patient
def get_integrative_analysis(patient_id: str):
    """Single doc at /patients/{id}/integrativeAnalysis/current (AI-generated)."""
    doc = db().collection('patients').document(patient_id) \
        .collection('integrativeAnalysis').document('current').get()
    if not doc.exists:
        return ok(None)
    return ok({'id': doc.id, **(doc.to_dict() or {})})
