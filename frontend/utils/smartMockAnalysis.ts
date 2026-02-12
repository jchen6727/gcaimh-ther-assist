/**
 * Smart Mock Analysis Generator
 *
 * Generates realistic, content-aware mock analysis responses based on
 * actual transcript content. This provides meaningful feedback even
 * without a backend, useful for development and demos.
 */

import { AnalysisResponse, SessionMetrics, Alert } from '../types/types';

// Keywords and patterns for analysis
const SAFETY_KEYWORDS = [
  'suicide', 'suicidal', 'kill myself', 'end my life', 'self-harm', 'cutting',
  'hurt myself', 'don\'t want to live', 'better off dead', 'no reason to live',
  'overdose', 'pills', 'gun', 'weapon'
];

const DISTRESS_KEYWORDS = [
  'panic', 'terrified', 'can\'t breathe', 'heart racing', 'shaking',
  'crying', 'sobbing', 'overwhelmed', 'can\'t cope', 'falling apart',
  'breaking down', 'losing it', 'freaking out'
];

const ANXIETY_KEYWORDS = [
  'anxious', 'worried', 'nervous', 'stressed', 'tense', 'on edge',
  'can\'t relax', 'racing thoughts', 'what if', 'fear', 'scared'
];

const POSITIVE_KEYWORDS = [
  'better', 'improving', 'hopeful', 'progress', 'helped', 'grateful',
  'thank you', 'makes sense', 'understand now', 'feeling good', 'relief'
];

const ENGAGEMENT_KEYWORDS = [
  'I think', 'I feel', 'I noticed', 'I realized', 'that makes sense',
  'I agree', 'yes', 'exactly', 'you\'re right', 'I see what you mean'
];

const RESISTANCE_KEYWORDS = [
  'I don\'t know', 'whatever', 'I guess', 'doesn\'t matter', 'won\'t work',
  'tried that', 'pointless', 'can\'t', 'impossible', 'no point'
];

const THERAPY_TECHNIQUES = {
  'cognitive restructuring': ['think differently', 'thought', 'belief', 'perspective', 'evidence'],
  'behavioral activation': ['activity', 'do something', 'schedule', 'routine', 'action'],
  'mindfulness': ['breathe', 'present', 'moment', 'aware', 'notice', 'observe'],
  'validation': ['understand', 'makes sense', 'valid', 'normal', 'reasonable'],
  'psychoeducation': ['explain', 'learn', 'understand why', 'brain', 'anxiety works'],
  'exposure': ['face', 'confront', 'approach', 'try', 'practice'],
  'grounding': ['five senses', 'feel', 'see', 'hear', 'touch', 'ground'],
  'reflection': ['sounds like', 'what I hear', 'reflect back', 'paraphrase'],
};

/**
 * Analyze transcript text for keyword presence
 */
const containsKeywords = (text: string, keywords: string[]): boolean => {
  const lowerText = text.toLowerCase();
  return keywords.some(keyword => lowerText.includes(keyword.toLowerCase()));
};

/**
 * Count keyword matches for scoring
 */
const countKeywordMatches = (text: string, keywords: string[]): number => {
  const lowerText = text.toLowerCase();
  return keywords.filter(keyword => lowerText.includes(keyword.toLowerCase())).length;
};

/**
 * Extract detected therapy techniques from transcript
 */
const detectTechniques = (text: string): string[] => {
  const detected: string[] = [];
  const lowerText = text.toLowerCase();

  for (const [technique, indicators] of Object.entries(THERAPY_TECHNIQUES)) {
    if (indicators.some(indicator => lowerText.includes(indicator))) {
      detected.push(technique);
    }
  }

  return detected;
};

/**
 * Determine emotional state from transcript content
 */
const determineEmotionalState = (text: string): SessionMetrics['emotional_state'] => {
  if (containsKeywords(text, SAFETY_KEYWORDS) || containsKeywords(text, DISTRESS_KEYWORDS)) {
    return 'distressed';
  }
  if (containsKeywords(text, ANXIETY_KEYWORDS)) {
    return 'anxious';
  }
  if (containsKeywords(text, POSITIVE_KEYWORDS)) {
    return 'calm';
  }
  if (containsKeywords(text, ENGAGEMENT_KEYWORDS)) {
    return 'engaged';
  }
  return 'unknown';
};

/**
 * Determine arousal level from transcript content
 */
const determineArousalLevel = (text: string): 'low' | 'moderate' | 'high' | 'elevated' | 'unknown' => {
  if (containsKeywords(text, SAFETY_KEYWORDS)) {
    return 'elevated';
  }
  if (containsKeywords(text, DISTRESS_KEYWORDS)) {
    return 'high';
  }
  if (containsKeywords(text, ANXIETY_KEYWORDS)) {
    return 'moderate';
  }
  if (containsKeywords(text, POSITIVE_KEYWORDS)) {
    return 'low';
  }
  return 'moderate';
};

/**
 * Calculate engagement level (0-1) from transcript
 */
const calculateEngagement = (text: string): number => {
  const engagementScore = countKeywordMatches(text, ENGAGEMENT_KEYWORDS);
  const resistanceScore = countKeywordMatches(text, RESISTANCE_KEYWORDS);

  // Base engagement
  let engagement = 0.5;

  // Adjust based on engagement vs resistance
  engagement += (engagementScore * 0.08);
  engagement -= (resistanceScore * 0.1);

  // Check for longer responses (more words = more engagement)
  const wordCount = text.split(' ').length;
  if (wordCount > 50) engagement += 0.1;
  if (wordCount > 100) engagement += 0.1;

  // Clamp between 0.2 and 0.95
  return Math.max(0.2, Math.min(0.95, engagement));
};

/**
 * Determine therapeutic alliance from interaction patterns
 */
const determineAlliance = (text: string): SessionMetrics['therapeutic_alliance'] => {
  const positiveIndicators = countKeywordMatches(text, [...POSITIVE_KEYWORDS, ...ENGAGEMENT_KEYWORDS]);
  const negativeIndicators = countKeywordMatches(text, RESISTANCE_KEYWORDS);

  const score = positiveIndicators - negativeIndicators;

  if (score >= 3) return 'strong';
  if (score >= 0) return 'moderate';
  return 'weak';
};

/**
 * Generate safety alert if needed
 */
const generateSafetyAlert = (text: string): Alert | null => {
  if (!containsKeywords(text, SAFETY_KEYWORDS)) {
    return null;
  }

  const hasSuicidalIdeation = containsKeywords(text, ['suicide', 'suicidal', 'kill myself', 'end my life']);
  const hasSelfHarm = containsKeywords(text, ['self-harm', 'cutting', 'hurt myself']);

  if (hasSuicidalIdeation) {
    return {
      timing: 'now',
      category: 'safety',
      title: 'Suicidal Ideation Detected',
      message: 'Patient has expressed thoughts of suicide. Conduct immediate risk assessment using Columbia Protocol or similar validated tool. Assess for plan, means, intent, and protective factors.',
      evidence: ['Patient verbalized suicidal thoughts'],
      recommendation: 'Conduct structured suicide risk assessment immediately. Consider safety planning and determine appropriate level of care.',
      immediateActions: [
        'Ask directly about suicidal thoughts, plan, and intent',
        'Assess access to means',
        'Identify protective factors',
        'Develop or review safety plan',
        'Consider consultation or higher level of care if indicated'
      ],
      contraindications: [
        'Do not minimize or dismiss the patient\'s statements',
        'Avoid leaving patient alone if actively suicidal',
        'Do not promise confidentiality if safety is at risk'
      ]
    };
  }

  if (hasSelfHarm) {
    return {
      timing: 'now',
      category: 'safety',
      title: 'Self-Harm Risk Identified',
      message: 'Patient has mentioned self-harm behaviors. Assess frequency, severity, function, and current urges.',
      evidence: ['Patient mentioned self-harm'],
      recommendation: 'Explore the function of self-harm and current urges. Discuss alternative coping strategies.',
      immediateActions: [
        'Assess current self-harm urges',
        'Review recent self-harm episodes',
        'Identify triggers and functions',
        'Discuss harm reduction if applicable'
      ]
    };
  }

  return null;
};

/**
 * Generate technique suggestion based on content
 */
const generateTechniqueSuggestion = (text: string, emotionalState: string): Alert | null => {
  if (containsKeywords(text, ANXIETY_KEYWORDS) && !containsKeywords(text, SAFETY_KEYWORDS)) {
    return {
      timing: 'pause',
      category: 'technique',
      title: 'Anxiety Management Opportunity',
      message: 'Patient is expressing anxiety symptoms. Consider introducing a grounding or breathing technique to help regulate arousal before continuing cognitive work.',
      evidence: ['Patient expressed anxiety-related language'],
      recommendation: 'Consider a brief grounding exercise or breathing technique to help the patient regulate before continuing.'
    };
  }

  if (containsKeywords(text, RESISTANCE_KEYWORDS)) {
    return {
      timing: 'pause',
      category: 'engagement',
      title: 'Patient Resistance Noted',
      message: 'Patient may be showing signs of resistance or disengagement. Consider exploring their concerns about the therapeutic approach or adjusting the pace.',
      evidence: ['Patient used resistance-indicating language'],
      recommendation: 'Validate the patient\'s experience and explore any concerns about the current approach. Consider whether a different technique might be more acceptable.'
    };
  }

  if (emotionalState === 'distressed') {
    return {
      timing: 'now',
      category: 'technique',
      title: 'Emotional Regulation Needed',
      message: 'Patient appears highly distressed. Prioritize emotional stabilization before continuing with cognitive or exploratory work.',
      evidence: ['High distress indicators in patient speech'],
      recommendation: 'Use grounding techniques, validation, and paced breathing to help regulate emotions before proceeding.',
      immediateActions: [
        'Slow the pace of the session',
        'Use a calming, validating tone',
        'Consider a brief grounding exercise',
        'Acknowledge the difficulty of the moment'
      ]
    };
  }

  return null;
};

/**
 * Generate process observation
 */
const generateProcessObservation = (engagement: number, alliance: string): Alert | null => {
  if (engagement > 0.8 && alliance === 'strong') {
    return {
      timing: 'info',
      category: 'process',
      title: 'Strong Therapeutic Engagement',
      message: 'Patient is showing excellent engagement and the therapeutic alliance appears strong. This is a good time for deeper exploratory work or introducing challenging material.',
      recommendation: 'Consider moving into deeper therapeutic work while engagement is high.'
    };
  }

  if (engagement < 0.4) {
    return {
      timing: 'pause',
      category: 'engagement',
      title: 'Low Engagement Detected',
      message: 'Patient engagement appears to be declining. Consider checking in about their experience of the session or shifting approach.',
      recommendation: 'Ask the patient about their experience of the session so far. Consider whether the current focus is resonating.'
    };
  }

  return null;
};

/**
 * Main function: Generate smart mock realtime analysis
 */
export const generateSmartRealtimeAnalysis = (
  transcriptSegment: Array<{ text: string; speaker?: string; timestamp?: string }>,
  sessionDurationMinutes: number,
  jobId: number
): AnalysisResponse => {
  // Combine all transcript text for analysis
  const fullText = transcriptSegment.map(t => t.text).join(' ');

  // Check for safety concerns first (highest priority)
  const safetyAlert = generateSafetyAlert(fullText);
  if (safetyAlert) {
    return {
      analysis_type: 'realtime',
      timestamp: new Date().toISOString(),
      session_phase: sessionDurationMinutes <= 10 ? 'beginning' : sessionDurationMinutes <= 40 ? 'middle' : 'end',
      alert: safetyAlert,
      job_id: jobId,
    } as any;
  }

  // Determine emotional state
  const emotionalState = determineEmotionalState(fullText);

  // Generate technique or process suggestion
  const techniqueAlert = generateTechniqueSuggestion(fullText, emotionalState);
  if (techniqueAlert) {
    return {
      analysis_type: 'realtime',
      timestamp: new Date().toISOString(),
      session_phase: sessionDurationMinutes <= 10 ? 'beginning' : sessionDurationMinutes <= 40 ? 'middle' : 'end',
      alert: techniqueAlert,
      job_id: jobId,
    } as any;
  }

  // Calculate engagement for process observations
  const engagement = calculateEngagement(fullText);
  const alliance = determineAlliance(fullText);

  const processAlert = generateProcessObservation(engagement, alliance);
  if (processAlert) {
    return {
      analysis_type: 'realtime',
      timestamp: new Date().toISOString(),
      session_phase: sessionDurationMinutes <= 10 ? 'beginning' : sessionDurationMinutes <= 40 ? 'middle' : 'end',
      alert: processAlert,
      job_id: jobId,
    } as any;
  }

  // Default: no alert needed, session proceeding normally
  return {
    analysis_type: 'realtime',
    timestamp: new Date().toISOString(),
    session_phase: sessionDurationMinutes <= 10 ? 'beginning' : sessionDurationMinutes <= 40 ? 'middle' : 'end',
    job_id: jobId,
    // No alert = session proceeding well
  } as any;
};

/**
 * Main function: Generate smart mock comprehensive analysis
 */
export const generateSmartComprehensiveAnalysis = (
  transcriptSegment: Array<{ text: string; speaker?: string; timestamp?: string }>,
  sessionDurationMinutes: number,
  jobId: number
): AnalysisResponse => {
  // Combine all transcript text for analysis
  const fullText = transcriptSegment.map(t => t.text).join(' ');

  // Calculate all metrics
  const emotionalState = determineEmotionalState(fullText);
  const arousalLevel = determineArousalLevel(fullText);
  const engagement = calculateEngagement(fullText);
  const alliance = determineAlliance(fullText);
  const techniques = detectTechniques(fullText);

  // Determine effectiveness based on engagement and alliance
  let effectiveness: 'effective' | 'struggling' | 'ineffective' | 'unknown' = 'unknown';
  if (engagement > 0.7 && (alliance === 'strong' || alliance === 'moderate')) {
    effectiveness = 'effective';
  } else if (engagement > 0.4) {
    effectiveness = 'struggling';
  } else if (engagement <= 0.4) {
    effectiveness = 'ineffective';
  }

  // Determine change urgency
  let changeUrgency: 'none' | 'monitor' | 'consider' | 'recommended' = 'none';
  if (effectiveness === 'ineffective') {
    changeUrgency = 'recommended';
  } else if (effectiveness === 'struggling') {
    changeUrgency = 'consider';
  } else if (containsKeywords(fullText, RESISTANCE_KEYWORDS)) {
    changeUrgency = 'monitor';
  }

  // Generate rationale based on analysis
  let rationale = '';
  if (containsKeywords(fullText, SAFETY_KEYWORDS)) {
    rationale = 'Safety concerns have been identified in this segment. Prioritize risk assessment and safety planning. Clinical judgment required for appropriate level of care.';
  } else if (effectiveness === 'effective') {
    rationale = `Current therapeutic approach appears effective. Patient engagement is high (${Math.round(engagement * 100)}%) and therapeutic alliance is ${alliance}. ${techniques.length > 0 ? `Techniques observed: ${techniques.join(', ')}.` : ''} Continue current approach.`;
  } else if (effectiveness === 'struggling') {
    rationale = `Current approach may need adjustment. Engagement level is moderate (${Math.round(engagement * 100)}%) with ${alliance} alliance. Consider checking in with patient about their experience of the session.`;
  } else {
    rationale = `Low engagement detected (${Math.round(engagement * 100)}%). Consider shifting therapeutic approach or exploring barriers to engagement.`;
  }

  return {
    analysis_type: 'comprehensive',
    timestamp: new Date().toISOString(),
    session_phase: sessionDurationMinutes <= 10 ? 'beginning' : sessionDurationMinutes <= 40 ? 'middle' : 'end',
    job_id: jobId,
    session_metrics: {
      engagement_level: engagement,
      therapeutic_alliance: alliance,
      techniques_detected: techniques.length > 0 ? techniques : ['active listening'],
      emotional_state: emotionalState,
      arousal_level: arousalLevel,
      phase_appropriate: true,
    },
    pathway_indicators: {
      current_approach_effectiveness: effectiveness,
      alternative_pathways: effectiveness !== 'effective' ? ['Consider motivational interviewing', 'Explore barriers to engagement'] : [],
      change_urgency: changeUrgency,
    },
    pathway_guidance: {
      rationale,
      immediate_actions: effectiveness !== 'effective'
        ? ['Check in with patient about session experience', 'Validate any difficulties', 'Consider adjusting pace or approach']
        : ['Continue current approach', 'Build on therapeutic momentum'],
      contraindications: containsKeywords(fullText, DISTRESS_KEYWORDS)
        ? ['Avoid challenging core beliefs while patient is dysregulated', 'Do not rush emotional processing']
        : [],
    },
    citations: [
      {
        citation_number: 1,
        source: {
          title: 'Evidence-Based Practice Guidelines',
          excerpt: 'Therapeutic alliance is a consistent predictor of treatment outcomes across modalities.',
        }
      }
    ],
  } as any;
};
