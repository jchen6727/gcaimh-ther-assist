"""
Seed test patient docs for dummy-mode integration testing.

Creates:
  /patients/patient-test-001  (Jane Doe, PTSD)
  /patients/patient-test-002  (Michael Chen, Anxiety)

These match the IDs in PORTAL_DEV_PATIENT_IDS env var on the backend.

Run with the same ADC as seed.py:
  python seed_test_data.py
"""
import sys
from google.cloud import firestore

PROJECT_ID = 'brk-prj-salvador-dura-bern-sbx'

PATIENTS = [
    {
        'id': 'patient-test-001',
        'name': 'Jane Doe',
        'status': 'active',
        'age': 42,
        'primaryConcern': 'PTSD, Depression',
        'focusTopics': 'trauma, avoidance, exposure',
    },
    {
        'id': 'patient-test-002',
        'name': 'Michael Chen',
        'status': 'active',
        'age': 35,
        'primaryConcern': 'PTSD, Nightmares',
        'focusTopics': 'trauma, sleep, hypervigilance',
    },
]


def main():
    db = firestore.Client(project=PROJECT_ID)
    print(f"Seeding {len(PATIENTS)} test patients to {PROJECT_ID}...")
    for p in PATIENTS:
        pid = p['id']
        data = {k: v for k, v in p.items() if k != 'id'}
        db.collection('patients').document(pid).set(data)
        print(f"  wrote /patients/{pid}: {data['name']}")
    print("Done.")


if __name__ == '__main__':
    sys.exit(main())
