"""
One-time catalog seeder for the patient/therapist portal.

Writes to Firestore collections:
  /modules                   ← PsychoeducationModule
  /interventions             ← Intervention
  /questionnaireDefinitions  ← QuestionnaireDefinition (includes items[])

Source: hand-curated content originally in
  frontend/contexts/ClientPortalContext.tsx (MOCK_MODULES, MOCK_INTERVENTIONS, MOCK_OUTCOME_MEASURES)
  frontend/providers/TherapistClientBridgeMockProvider.ts (SEED_QUESTIONNAIRE_DEFS)

Usage:
  python seed.py                # writes to Firestore in current ADC project
  python seed.py --dry-run      # prints what it would write, no Firestore call
  python seed.py --force        # overwrites existing docs (default: skip if exists)
"""
import argparse
import sys
from google.cloud import firestore

PROJECT_ID = "brk-prj-salvador-dura-bern-sbx"

# ─── MODULES (29 from MOCK_MODULES) ─────────────────────────────────

MODULES = [
    # A) Body, Emotion & Regulation
    {'id': 'mod-stress-response', 'title': 'The Stress Response', 'category': 'A) Body, Emotion & Regulation', 'estimatedMinutes': 8, 'summary': 'How the fight-flight-freeze system works, and why your body reacts before your mind catches up.', 'tags': ['stress', 'nervous-system', 'regulation']},
    {'id': 'mod-emotion-functions', 'title': 'What Emotions Are For', 'category': 'A) Body, Emotion & Regulation', 'estimatedMinutes': 7, 'summary': 'Every emotion carries information. Learn the adaptive function of anger, sadness, fear, and guilt.', 'tags': ['emotions', 'psychoeducation', 'awareness']},
    {'id': 'mod-interoception-panic', 'title': 'Interoception & Panic', 'category': 'A) Body, Emotion & Regulation', 'estimatedMinutes': 9, 'summary': 'Why misreading body signals can trigger panic, and how interoceptive awareness helps.', 'tags': ['panic', 'body-awareness', 'anxiety']},
    # B) Attention & Repetitive Thought
    {'id': 'mod-attentional-bias', 'title': 'Attentional Bias', 'category': 'B) Attention & Repetitive Thought', 'estimatedMinutes': 7, 'summary': 'Your brain highlights threats automatically. Understand why and how to retrain the spotlight.', 'tags': ['attention', 'anxiety', 'CBT']},
    {'id': 'mod-rumination-worry', 'title': 'Rumination & Worry', 'category': 'B) Attention & Repetitive Thought', 'estimatedMinutes': 8, 'summary': 'The difference between productive problem-solving and the sticky loops of rumination and worry.', 'tags': ['rumination', 'worry', 'metacognition']},
    {'id': 'mod-cognitive-load', 'title': 'Cognitive Load & Decision Fatigue', 'category': 'B) Attention & Repetitive Thought', 'estimatedMinutes': 6, 'summary': 'Why your brain makes worse choices when overloaded, and strategies to protect mental bandwidth.', 'tags': ['executive-function', 'fatigue', 'self-management']},
    # C) Thinking Patterns
    {'id': 'mod-cognitive-distortions', 'title': 'Cognitive Distortions Overview', 'category': 'C) Thinking Patterns', 'estimatedMinutes': 10, 'summary': 'An introduction to the most common thinking traps that keep anxiety and low mood going.', 'tags': ['CBT', 'cognitive-distortion', 'psychoeducation']},
    {'id': 'mod-catastrophizing', 'title': 'Understanding Catastrophizing', 'category': 'C) Thinking Patterns', 'estimatedMinutes': 8, 'summary': 'Recognize and challenge catastrophic thinking that amplifies anxiety.', 'tags': ['anxiety', 'CBT', 'cognitive-distortion']},
    {'id': 'mod-black-white-thinking', 'title': 'All-or-Nothing Thinking', 'category': 'C) Thinking Patterns', 'estimatedMinutes': 6, 'summary': 'Soften extreme black-and-white thinking patterns into more balanced perspectives.', 'tags': ['perfectionism', 'CBT', 'cognitive-distortion']},
    {'id': 'mod-confirmation-bias', 'title': 'Confirmation Bias', 'category': 'C) Thinking Patterns', 'estimatedMinutes': 7, 'summary': 'How the mind seeks evidence that fits existing beliefs and ignores what contradicts them.', 'tags': ['bias', 'critical-thinking', 'CBT']},
    {'id': 'mod-cognitive-dissonance', 'title': 'Cognitive Dissonance', 'category': 'C) Thinking Patterns', 'estimatedMinutes': 8, 'summary': 'The uncomfortable tension when actions and beliefs clash, and why it drives change or avoidance.', 'tags': ['motivation', 'self-awareness', 'behavior-change']},
    # D) Avoidance & Maintenance Loops
    {'id': 'mod-avoidance', 'title': 'The Avoidance Trap', 'category': 'D) Avoidance & Maintenance Loops', 'estimatedMinutes': 8, 'summary': 'Short-term relief, long-term cost. How avoidance maintains anxiety and shrinks your world.', 'tags': ['avoidance', 'anxiety', 'exposure']},
    {'id': 'mod-reassurance-seeking', 'title': 'Reassurance Seeking', 'category': 'D) Avoidance & Maintenance Loops', 'estimatedMinutes': 7, 'summary': 'Why asking "Are you sure it will be okay?" feels good but feeds the anxiety cycle.', 'tags': ['OCD', 'anxiety', 'maintenance']},
    # E) Learning, Habits & Behavior Change
    {'id': 'mod-neuroplasticity', 'title': 'Neuroplasticity Basics', 'category': 'E) Learning, Habits & Behavior Change', 'estimatedMinutes': 8, 'summary': 'Your brain physically rewires with practice. The science behind why therapy homework matters.', 'tags': ['neuroscience', 'motivation', 'learning']},
    {'id': 'mod-reinforcement', 'title': 'Reinforcement & Punishment', 'category': 'E) Learning, Habits & Behavior Change', 'estimatedMinutes': 7, 'summary': 'The building blocks of behavioral learning: what strengthens habits and what weakens them.', 'tags': ['behaviorism', 'habits', 'learning']},
    {'id': 'mod-habit-loop', 'title': 'The Habit Loop', 'category': 'E) Learning, Habits & Behavior Change', 'estimatedMinutes': 8, 'summary': 'Cue, routine, reward: understanding the anatomy of habits so you can redesign them.', 'tags': ['habits', 'behavior-change', 'self-management']},
    {'id': 'mod-extinction', 'title': 'Extinction & Spontaneous Recovery', 'category': 'E) Learning, Habits & Behavior Change', 'estimatedMinutes': 9, 'summary': 'Why feared situations feel scary again after progress, and why that is completely normal.', 'tags': ['exposure', 'anxiety', 'learning']},
    # F) Compulsion & Addiction Spectrum
    {'id': 'mod-craving-dynamics', 'title': 'Craving Dynamics', 'category': 'F) Compulsion & Addiction Spectrum', 'estimatedMinutes': 8, 'summary': 'How cravings build, peak, and naturally pass if you ride the wave instead of acting on them.', 'tags': ['craving', 'urge-surfing', 'addiction']},
    {'id': 'mod-compulsive-loops', 'title': 'Compulsive Loops', 'category': 'F) Compulsion & Addiction Spectrum', 'estimatedMinutes': 9, 'summary': "The brain mechanism behind \"I know I should stop but I can’t\" and how to interrupt the loop.", 'tags': ['OCD', 'compulsion', 'impulse-control']},
    # G) Self, Identity & Social Systems
    {'id': 'mod-self-criticism', 'title': 'The Inner Critic', 'category': 'G) Self, Identity & Social Systems', 'estimatedMinutes': 9, 'summary': 'Where self-criticism comes from, why it feels protective, and how self-compassion works better.', 'tags': ['self-compassion', 'shame', 'self-esteem']},
    {'id': 'mod-narrative-identity', 'title': 'Narrative Identity', 'category': 'G) Self, Identity & Social Systems', 'estimatedMinutes': 10, 'summary': 'The stories you tell about yourself shape how you feel. Learn to edit the narrative mindfully.', 'tags': ['identity', 'narrative-therapy', 'meaning']},
    {'id': 'mod-attachment', 'title': 'Attachment Styles', 'category': 'G) Self, Identity & Social Systems', 'estimatedMinutes': 12, 'summary': 'How early relationships wire expectations about closeness, trust, and safety in adult bonds.', 'tags': ['attachment', 'relationships', 'developmental']},
    # H) Foundations
    {'id': 'mod-sleep', 'title': 'Sleep & Mental Health', 'category': 'H) Foundations', 'estimatedMinutes': 8, 'summary': 'Why sleep is the foundation of emotional regulation and practical sleep-hygiene strategies.', 'tags': ['sleep', 'hygiene', 'foundations']},
    {'id': 'mod-food', 'title': 'Nutrition & Mood', 'category': 'H) Foundations', 'estimatedMinutes': 7, 'summary': 'The gut-brain connection, blood-sugar effects on anxiety, and simple nutritional principles.', 'tags': ['nutrition', 'gut-brain', 'foundations']},
    {'id': 'mod-physical-activity', 'title': 'Movement as Medicine', 'category': 'H) Foundations', 'estimatedMinutes': 6, 'summary': 'How even brief movement changes brain chemistry and why exercise is an evidence-based intervention.', 'tags': ['exercise', 'dopamine', 'foundations']},
    # I) Trauma-Informed
    {'id': 'mod-trauma-memory', 'title': 'How Trauma Memories Work', 'category': 'I) Trauma-Informed', 'estimatedMinutes': 10, 'summary': 'Why traumatic memories feel like they are happening now, and how processing helps them become past-tense.', 'tags': ['trauma', 'memory', 'PTSD']},
    {'id': 'mod-dissociation', 'title': 'Understanding Dissociation', 'category': 'I) Trauma-Informed', 'estimatedMinutes': 11, 'summary': "Dissociation as the brain’s emergency brake. Recognizing the spectrum from zoning out to depersonalization.", 'tags': ['dissociation', 'trauma', 'grounding']},
]

# ─── INTERVENTIONS (4 from MOCK_INTERVENTIONS) ──────────────────────

INTERVENTIONS = [
    {'id': 'int-box-breathing', 'title': 'Box Breathing', 'type': 'BREATHWORK', 'description': 'Equal 4-count inhale, hold, exhale, hold. Calms the nervous system rapidly.', 'durationSeconds': 120},
    {'id': 'int-grounding', 'title': '5-4-3-2-1 Grounding', 'type': 'GROUNDING', 'description': 'Sensory anchoring exercise: 5 see, 4 hear, 3 feel, 2 smell, 1 taste.', 'durationSeconds': 60},
    {'id': 'int-cognitive-reframe', 'title': 'Cognitive Reframe', 'type': 'COGNITIVE', 'description': 'Guided thought record: identify distortion, weigh evidence, form balanced thought.', 'durationSeconds': 180},
    {'id': 'int-progressive-muscle', 'title': 'Progressive Muscle Relaxation', 'type': 'BODY_AWARENESS', 'description': 'Systematically tense and release muscle groups to reduce physical tension.', 'durationSeconds': 300},
]

# ─── QUESTIONNAIRES (PHQ-9, GAD-7) — canonical with items[] ────────

LIKERT_OPTIONS = [
    {'value': 0, 'label': 'Not at all'},
    {'value': 1, 'label': 'Several days'},
    {'value': 2, 'label': 'More than half the days'},
    {'value': 3, 'label': 'Nearly every day'},
]

PHQ9_ITEMS = [
    'Little interest or pleasure in doing things',
    'Feeling down, depressed, or hopeless',
    'Trouble falling or staying asleep, or sleeping too much',
    'Feeling tired or having little energy',
    'Poor appetite or overeating',
    "Feeling bad about yourself — or that you are a failure",
    'Trouble concentrating on things',
    'Moving or speaking slowly, or being fidgety/restless',
    'Thoughts that you would be better off dead, or hurting yourself',
]

GAD7_ITEMS = [
    'Feeling nervous, anxious, or on edge',
    'Not being able to stop or control worrying',
    'Worrying too much about different things',
    'Trouble relaxing',
    'Being so restless that it is hard to sit still',
    'Becoming easily annoyed or irritable',
    'Feeling afraid, as if something awful might happen',
]

QUESTIONNAIRES = [
    {
        'id': 'phq9',
        'name': 'Patient Health Questionnaire-9',
        'shortName': 'PHQ-9',
        'description': 'Screens for depression severity over the past 2 weeks.',
        'category': 'DEPRESSION',
        'items': [{'id': f'phq9-{i}', 'text': t, 'options': LIKERT_OPTIONS} for i, t in enumerate(PHQ9_ITEMS)],
        'maxScore': 27,
        'estimatedMinutes': 5,
        'scoring': 'sum',
        'cadence': 'weekly',
        'thresholds': [
            {'label': 'Minimal', 'min': 0, 'max': 4, 'color': 'success'},
            {'label': 'Mild', 'min': 5, 'max': 9, 'color': 'info'},
            {'label': 'Moderate', 'min': 10, 'max': 14, 'color': 'warning'},
            {'label': 'Moderately Severe', 'min': 15, 'max': 19, 'color': 'error'},
            {'label': 'Severe', 'min': 20, 'max': 27, 'color': 'error'},
        ],
    },
    {
        'id': 'gad7',
        'name': 'Generalized Anxiety Disorder-7',
        'shortName': 'GAD-7',
        'description': 'Measures generalized anxiety severity over the past 2 weeks.',
        'category': 'ANXIETY',
        'items': [{'id': f'gad7-{i}', 'text': t, 'options': LIKERT_OPTIONS} for i, t in enumerate(GAD7_ITEMS)],
        'maxScore': 21,
        'estimatedMinutes': 4,
        'scoring': 'sum',
        'cadence': 'weekly',
        'thresholds': [
            {'label': 'Minimal', 'min': 0, 'max': 4, 'color': 'success'},
            {'label': 'Mild', 'min': 5, 'max': 9, 'color': 'info'},
            {'label': 'Moderate', 'min': 10, 'max': 14, 'color': 'warning'},
            {'label': 'Severe', 'min': 15, 'max': 21, 'color': 'error'},
        ],
    },
]


def seed(collection_name: str, docs: list, dry_run: bool, force: bool, db) -> None:
    print(f"\n=== {collection_name} ({len(docs)} docs) ===")
    if dry_run:
        for d in docs:
            print(f"  [dry-run] would write {collection_name}/{d['id']}")
        return
    coll = db.collection(collection_name)
    for d in docs:
        doc_id = d['id']
        ref = coll.document(doc_id)
        if ref.get().exists and not force:
            print(f"  skip {doc_id} (exists, use --force to overwrite)")
            continue
        ref.set(d)
        print(f"  wrote {doc_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true', help='overwrite existing docs')
    parser.add_argument('--project', default=PROJECT_ID)
    args = parser.parse_args()

    db = firestore.Client(project=args.project) if not args.dry_run else None
    seed('modules', MODULES, args.dry_run, args.force, db)
    seed('interventions', INTERVENTIONS, args.dry_run, args.force, db)
    seed('questionnaireDefinitions', QUESTIONNAIRES, args.dry_run, args.force, db)
    print("\nDone.")


if __name__ == '__main__':
    sys.exit(main())
