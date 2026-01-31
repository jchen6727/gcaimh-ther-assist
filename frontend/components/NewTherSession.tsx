import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Chip,
  useTheme,
  useMediaQuery,
  IconButton,
  Fab,
  Tooltip,
  Drawer,
  Badge,
  CircularProgress,
  Alert as MuiAlert,
  Collapse,
  LinearProgress,
} from '@mui/material';
import {
  HealthAndSafety,
  NaturePeople,
  Category,
  Exposure,
  Check,
  Warning,
  Psychology,
  Timeline,
  Stop,
  FiberManualRecord,
  ArrowBack,
  Search,
  CallSplit,
  Route,
  Mic,
  Pause,
  PlayArrow,
  Chat,
  Close,
  VolumeUp,
  Article,
  Info,
  TrendingUp,
  ExpandLess,
  ExpandMore,
  Shield,
  SwapHoriz,
  Lightbulb,
  Assessment,
  Build,
  ContactSupport,
  Explore,
  UploadFile,
} from '@mui/icons-material';
import { Alert, SessionMetrics, PathwayIndicators, SessionContext, Alert as IAlert, Citation, SessionSummary } from '../types/types';
import { formatDuration } from '../utils/timeUtils';
import { getStatusColor } from '../utils/colorUtils';
import { renderMarkdown } from '../utils/textRendering';
import { processNewAlert, cleanupOldAlerts } from '../utils/alertDeduplication';
import { mockPatients } from '../utils/mockPatients';
import { testTranscriptData, TestTranscriptEntry } from '../utils/mockTranscript';
import { ChartDataPoint, createChartDataPoint, pruneChartData } from '../utils/chartDataUtils';
// Mock chart data generator removed - analysis now builds chart data from actual responses
import SessionLineChart from './SessionLineChart';
import ActionDetailsPanel from './ActionDetailsPanel';
import EvidenceTab from './EvidenceTab';
import PathwayTab from './PathwayTab';
import GuidanceTab from './GuidanceTab';
import AlternativesTab from './AlternativesTab';
import TranscriptDisplay from './TranscriptDisplay';
import SessionSummaryModal from './SessionSummaryModal';
import RationaleModal from './RationaleModal';
import CitationModal from './CitationModal';
import TherapistNotesPanel from './TherapistNotesPanel';
import { useAudioStreamingWebSocketTher } from '../hooks/useAudioStreamingWebSocketTher';
import { useTherapyAnalysis } from '../hooks/useTherapyAnalysis';
import { useAuth } from '../contexts/AuthContext';
import BackendStatusIndicator from './BackendStatusIndicator';
import ActivityLog, { ActivityLogEntry } from './ActivityLog';

interface NewTherSessionProps {
  onNavigateBack?: () => void;
  onStopRecording?: () => void;
  patientId?: string | null;
  alerts?: Alert[];
  sessionMetrics?: SessionMetrics;
  pathwayIndicators?: PathwayIndicators;
  sessionDuration?: number;
  sessionPhase?: string;
  sessionId?: string;
  currentGuidance?: {
    title: string;
    time: string;
    content: string;
    immediateActions: Array<{
      title: string;
      description: string;
      icon: 'safety' | 'grounding';
    }>;
    contraindications: Array<{
      title: string;
      description: string;
      icon: 'cognitive' | 'exposure';
    }>;
  };
}

const NewTherSession: React.FC<NewTherSessionProps> = ({
  onNavigateBack,
  patientId,
}) => {
  const { currentUser } = useAuth();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  const isWideScreen = useMediaQuery('(min-width:1024px)');
  
  // Generate a unique session instance ID for localStorage namespacing (once per page load)
  const [sessionInstanceId] = useState(() => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    // Fallback for older browsers
    return `${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
  });

  // Core session state
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [sessionType, setSessionType] = useState<'microphone' | 'test' | 'audio' | null>(null);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [sessionStartTime, setSessionStartTime] = useState<Date | null>(null);
  const [pausedTime, setPausedTime] = useState(0);
  const [lastPauseTime, setLastPauseTime] = useState<Date | null>(null);
  const [sessionDuration, setSessionDuration] = useState(0);
  
  // Transcript and analysis state
  const [transcript, setTranscript] = useState<Array<{
    text: string;
    timestamp: string;
    is_interim?: boolean;
  }>>([]);
  const [alerts, setAlerts] = useState<IAlert[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [sessionMetrics, setSessionMetrics] = useState({
    engagement_level: 0.0,
    therapeutic_alliance: 'unknown' as 'strong' | 'moderate' | 'weak' | 'unknown',
    techniques_detected: [] as string[],
    emotional_state: 'unknown' as 'calm' | 'anxious' | 'distressed' | 'dissociated' | 'engaged' | 'unknown',
    arousal_level: 'unknown' as 'low' | 'moderate' | 'high' | 'elevated' | 'unknown',
    phase_appropriate: false,
  });
  const [pathwayIndicators, setPathwayIndicators] = useState({
    current_approach_effectiveness: 'unknown' as 'effective' | 'struggling' | 'ineffective' | 'unknown',
    alternative_pathways: [] as string[],
    change_urgency: 'monitor' as 'none' | 'monitor' | 'consider' | 'recommended',
  });
  const [pathwayGuidance, setPathwayGuidance] = useState<{
    rationale?: string;
    immediate_actions?: string[];
    contraindications?: string[];
    alternative_pathways?: Array<{
      approach: string;
      reason: string;
      techniques: string[];
    }>;
  }>({});
  const [pathwayHistory, setPathwayHistory] = useState<Array<{
    timestamp: string;
    effectiveness: 'effective' | 'struggling' | 'ineffective' | 'unknown';
    change_urgency: 'none' | 'monitor' | 'consider' | 'recommended';
    rationale?: string;
  }>>([]);
  
  // Chart data state - collects data from comprehensive analysis regardless of UI blocking
  const [chartDataHistory, setChartDataHistory] = useState<ChartDataPoint[]>([]);
  
  // UI state
  const [activeTab, setActiveTab] = useState<'guidance' | 'evidence' | 'pathway' | 'alternatives'>('guidance');
  const [selectedAction, setSelectedAction] = useState<any>(null);
  const [selectedCitation, setSelectedCitation] = useState<any>(null);
  const [isContraindication, setIsContraindication] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [newTranscriptCount, setNewTranscriptCount] = useState(0);
  const [selectedAlertIndex, setSelectedAlertIndex] = useState<number | null>(null);
  
  // Session context for AI analysis — derived from patient data
  const [sessionContext] = useState<SessionContext>(() => {
    if (patientId) {
      const patient = mockPatients.find(p => p.id === patientId);
      if (patient?.focusTopics) {
        // Parse focusTopics to extract primary concern and approach
        const topics = patient.focusTopics.split(',').map(t => t.trim());
        const primaryConcern = topics[0] || 'General';

        // Infer session type / approach from focus topics
        const topicsLower = patient.focusTopics.toLowerCase();
        let sessionType = 'CBT';
        let currentApproach = 'Cognitive Behavioral Therapy';
        if (topicsLower.includes('emdr')) {
          sessionType = 'EMDR';
          currentApproach = 'EMDR Therapy';
        } else if (topicsLower.includes('exposure therapy')) {
          sessionType = 'Exposure';
          currentApproach = 'Exposure and Response Prevention';
        } else if (topicsLower.includes('behavioral activation')) {
          sessionType = 'BA';
          currentApproach = 'Behavioral Activation';
        } else if (topicsLower.includes('act')) {
          sessionType = 'ACT';
          currentApproach = 'Acceptance and Commitment Therapy';
        } else if (topicsLower.includes('dbt')) {
          sessionType = 'DBT';
          currentApproach = 'Dialectical Behavior Therapy';
        }

        return {
          session_type: sessionType,
          primary_concern: primaryConcern,
          current_approach: currentApproach,
        };
      }
    }
    // Default when no patient selected (e.g. quick session launch)
    return {
      session_type: 'CBT',
      primary_concern: 'General',
      current_approach: 'Cognitive Behavioral Therapy',
    };
  });
  
  // Analysis tracking
  const [wordsSinceLastAnalysis, setWordsSinceLastAnalysis] = useState(0);
  const [hasReceivedComprehensiveAnalysis, setHasReceivedComprehensiveAnalysis] = useState(false);
  
  // Analysis job ID tracking - counter to relate realtime and comprehensive results
  const analysisJobCounterRef = useRef(0);
  
  // Track currently displayed job IDs to ensure realtime and comprehensive results match
  const [displayedRealtimeJobId, setDisplayedRealtimeJobId] = useState<number | null>(null);
  const [displayedComprehensiveJobId, setDisplayedComprehensiveJobId] = useState<number | null>(null);
  const [waitingForComprehensiveJobId, setWaitingForComprehensiveJobId] = useState<number | null>(null);
  
  // Use refs to avoid closure issues in useTherapyAnalysis callback
  const waitingForComprehensiveJobIdRef = useRef<number | null>(null);
  const displayedRealtimeJobIdRef = useRef<number | null>(null);
  const displayedComprehensiveJobIdRef = useRef<number | null>(null);
  
  // Session summary state
  const [showSessionSummary, setShowSessionSummary] = useState(false);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [sessionSummaryClosed, setSessionSummaryClosed] = useState(false);
  
  // Modal state
  const [showRationaleModal, setShowRationaleModal] = useState(false);
  const [citationModalOpen, setCitationModalOpen] = useState(false);
  const [selectedCitationModal, setSelectedCitationModal] = useState<Citation | null>(null);
  
  // Test mode state
  const [isTestMode, setIsTestMode] = useState(false);
  const testIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const activeTranscriptDataRef = useRef<TestTranscriptEntry[]>(testTranscriptData);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Error and loading state
  const [error, setError] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Activity log state for LLM diagnostics
  const [activityLogEntries, setActivityLogEntries] = useState<ActivityLogEntry[]>([]);
  const activityLogIdCounter = useRef(0);

  const addLogEntry = useCallback((
    model: string,
    analysisType: string,
    phase: 'started' | 'complete' | 'error',
    summary: string,
    details?: ActivityLogEntry['details']
  ) => {
    activityLogIdCounter.current += 1;
    const now = new Date();
    const ts = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    const entry: ActivityLogEntry = {
      id: `log-${activityLogIdCounter.current}`,
      timestamp: ts,
      model,
      analysisType,
      phase,
      summary,
      details,
    };
    setActivityLogEntries(prev => [...prev.slice(-200), entry]); // Keep last 200
  }, []);

  // Audio streaming hook with WebSocket for both microphone and file
  const { 
    isConnected, 
    startMicrophoneRecording, 
    startAudioFileStreaming,
    pauseAudioStreaming,
    resumeAudioStreaming,
    stopStreaming, 
    isPlayingAudio,
    audioProgress,
    sessionId 
  } = useAudioStreamingWebSocketTher({
    authToken,
    onTranscript: (newTranscript: any) => {
      if (newTranscript.is_interim) {
        setTranscript(prev => {
          const newEntry = {
            text: newTranscript.transcript || '',
            timestamp: newTranscript.timestamp || new Date().toISOString(),
            is_interim: true,
          };
          
          if (prev.length > 0 && prev[prev.length - 1].is_interim) {
            return [...prev.slice(0, -1), newEntry];
          }
          return [...prev, newEntry];
        });
      } else {
        setTranscript(prev => {
          const filtered = prev.filter(entry => !entry.is_interim);
          return [...filtered, {
            text: newTranscript.transcript || '',
            timestamp: newTranscript.timestamp || new Date().toISOString(),
            is_interim: false,
          }];
        });
        
        if (!transcriptOpen) {
          setNewTranscriptCount(prev => prev + 1);
        }
      }
    },
    onError: (error: string) => {
      console.error('Streaming error (not shown to user):', error);
    }
  });

  // Get Firebase auth token
  useEffect(() => {
    const getAuthToken = async () => {
      if (currentUser) {
        try {
          const token = await currentUser.getIdToken();
          setAuthToken(token);
        } catch (error) {
          console.error('Error getting auth token:', error);
          setAuthToken(null);
        }
      } else {
        setAuthToken(null);
      }
    };

    getAuthToken();
  }, [currentUser]);

  // Track logged analyses to prevent duplicate logs in Strict Mode
  const lastLoggedAnalysisRef = useRef<Set<string>>(new Set());

  const { analyzeSegment, generateSessionSummary } = useTherapyAnalysis({
    authToken,
    onAnalysis: (analysis) => {
      const analysisType = (analysis as any).analysis_type;
      const isRealtime = analysisType === 'realtime';
      const jobId = (analysis as any).job_id;
      
      // Create a unique identifier for this analysis to prevent duplicate logs
      const analysisId = `${analysisType}-${Date.now()}-${JSON.stringify(analysis).length}`;
      
      // Only log if we haven't logged this analysis before (prevents Strict Mode duplicate logs)
      if (!lastLoggedAnalysisRef.current.has(analysisId)) {
        lastLoggedAnalysisRef.current.add(analysisId);

        // Clean up old entries to prevent memory leaks (keep only last 50)
        if (lastLoggedAnalysisRef.current.size > 50) {
          const entries = Array.from(lastLoggedAnalysisRef.current);
          lastLoggedAnalysisRef.current = new Set(entries.slice(-25));
        }

        // Log diagnostics from backend _diagnostics field
        const diag = (analysis as any)._diagnostics;
        if (diag) {
          // Build result summary based on analysis type
          let resultSummary = '';
          if (isRealtime && analysis.alert) {
            resultSummary = `Alert: ${analysis.alert.category} (${analysis.alert.timing}) - "${analysis.alert.title || ''}"`;
          } else if (!isRealtime && analysis.session_metrics) {
            const m = analysis.session_metrics;
            resultSummary = `engagement=${Math.round((m.engagement_level || 0) * 100)}%, alliance=${m.therapeutic_alliance || '?'}, emotional=${m.emotional_state || '?'}`;
          }

          addLogEntry(
            diag.model || (isRealtime ? 'flash' : 'pro'),
            diag.analysis_type || analysisType,
            diag.json_parse_success === false ? 'error' : 'complete',
            `${analysisType} analysis complete (Job ${jobId})`,
            {
              prompt: diag.prompt_used,
              temperature: diag.temperature,
              maxTokens: diag.max_output_tokens,
              thinkingBudget: diag.thinking_budget,
              ragTools: diag.rag_tools,
              latencyMs: diag.latency_ms,
              ttftMs: diag.ttft_ms,
              tokenUsage: diag.token_usage,
              finishReason: diag.finish_reason,
              groundingChunks: diag.grounding?.chunks_retrieved,
              groundingSources: diag.grounding?.sources,
              responseLength: diag.response_length_chars,
              jsonParseSuccess: diag.json_parse_success,
              usedFallback: diag.used_fallback,
              triggerPhrase: diag.trigger_phrase_detected,
              resultSummary,
            }
          );
        }
      }

      if (isRealtime) {
        // Real-time analysis: Only update alerts and set up for comprehensive results
        if (analysis.alert) {
          const newAlert = {
            ...analysis.alert,
            sessionTime: sessionDuration,
            timestamp: new Date().toISOString(),
            jobId: jobId // Store jobId with alert
          };

          setAlerts(prev => {
            const result = processNewAlert(newAlert, prev);

            if (result.shouldAdd) {
              const updatedAlerts = [newAlert, ...prev].slice(0, 8);
              
              // Update displayed realtime job ID and prepare for comprehensive results
              setDisplayedRealtimeJobId(jobId);
              setWaitingForComprehensiveJobId(jobId);
              
              // Clear previous comprehensive results since we have new realtime results
              setDisplayedComprehensiveJobId(null);
              setPathwayGuidance({});
              setCitations([]);
              
              // Create unique log identifier for this specific alert
              const alertLogId = `new-alert-${newAlert.timestamp}-${newAlert.title}`;
              if (!lastLoggedAnalysisRef.current.has(alertLogId)) {
                lastLoggedAnalysisRef.current.add(alertLogId);
                console.log(`[Session] ⚠️ New ${newAlert.category} alert: "${newAlert.title}" (${newAlert.timing}) - Job ID: ${jobId}`);
              }
              
              return updatedAlerts;
            } else {
              const reason = result.blockReason || 'deduplication rules';
              
              // Create unique log identifier for this specific filter event
              const filterLogId = `filter-alert-${Date.now()}-${analysis.alert?.title || 'unknown'}`;
              if (!lastLoggedAnalysisRef.current.has(filterLogId)) {
                lastLoggedAnalysisRef.current.add(filterLogId);
                console.log(`[Session] 🚫 Realtime alert filtered: ${reason} - Job ID: ${jobId}`, analysis.alert);
              }
              
              return prev;
            }
          });
        }
      } else {
        // Comprehensive RAG analysis: Always collect chart data, but conditionally update UI
        
        // ALWAYS collect chart data and update session metrics from comprehensive analysis
        if (analysis.session_metrics) {
          // Always update session metrics from comprehensive analysis
          setSessionMetrics(prev => ({
            ...prev,
            ...analysis.session_metrics
          }));

          if (analysis.pathway_indicators) {
            const newChartDataPoint = createChartDataPoint(
              analysis.session_metrics,
              analysis.pathway_indicators,
              sessionDurationRef.current,
              jobId
            );

            setChartDataHistory(prev => {
              const updatedHistory = [...prev, newChartDataPoint];
              // Prune to keep reasonable size
              return pruneChartData(updatedHistory, 100);
            });

            console.log(`[Session] 📊 Chart data collected - Job ID: ${jobId}, Engagement: ${Math.round(analysis.session_metrics.engagement_level * 100)}%, Alliance: ${analysis.session_metrics.therapeutic_alliance}`);
          }
        }

        // Conditionally update pathway guidance based on job ID matching
        const currentWaitingJobId = waitingForComprehensiveJobIdRef.current;
        if (jobId && jobId === currentWaitingJobId) {
          setHasReceivedComprehensiveAnalysis(true);
          setDisplayedComprehensiveJobId(jobId);
          setWaitingForComprehensiveJobId(null);

          console.log(`[Session] 📋 Comprehensive results matched for pathway guidance - Job ID: ${jobId}`);
          
          if (analysis.pathway_indicators) {
            const newIndicators = analysis.pathway_indicators;
            
            // Check if there's a change in urgency or effectiveness to add to history
            if (pathwayIndicators.change_urgency !== newIndicators.change_urgency ||
                pathwayIndicators.current_approach_effectiveness !== newIndicators.current_approach_effectiveness) {
              setPathwayHistory(prev => [...prev, {
                timestamp: new Date().toISOString(),
                effectiveness: newIndicators.current_approach_effectiveness || 'unknown',
                change_urgency: newIndicators.change_urgency || 'none',
                rationale: (analysis as any).pathway_guidance?.rationale
              }].slice(-10));
            }
            
            setPathwayIndicators(prev => ({
              ...prev,
              ...newIndicators
            }));
          }
          
          if ((analysis as any).pathway_guidance) {
            setPathwayGuidance((analysis as any).pathway_guidance);
          }
          
          if (analysis.citations) {
            setCitations(analysis.citations);
          }
        } else {
          console.log(`[Session] 🚫 Comprehensive results ignored for UI - Job ID: ${jobId} (waiting for: ${currentWaitingJobId})`);
        }
      }
    },
  });

  // Update session duration every second (accounting for paused time)
  useEffect(() => {
    if (!isRecording || !sessionStartTime || isPaused) return;

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = Math.floor((now - sessionStartTime.getTime()) / 1000);
      setSessionDuration(elapsed - pausedTime);
    }, 1000);

    return () => clearInterval(interval);
  }, [isRecording, sessionStartTime, isPaused, pausedTime]);

  // Store analysis functions in refs to avoid recreating intervals
  const analyzeSegmentRef = useRef(analyzeSegment);
  
  // Store transcript in ref to avoid stale closures
  const transcriptRef = useRef(transcript);
  const sessionMetricsRef = useRef(sessionMetrics);
  const alertsRef = useRef(alerts);
  const sessionContextRef = useRef(sessionContext);
  const sessionDurationRef = useRef(sessionDuration);
  
  useEffect(() => {
    analyzeSegmentRef.current = analyzeSegment;
  }, [analyzeSegment]);
  
  // Update refs when state changes
  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);
  
  useEffect(() => {
    sessionMetricsRef.current = sessionMetrics;
  }, [sessionMetrics]);
  
  useEffect(() => {
    alertsRef.current = alerts;
  }, [alerts]);
  
  useEffect(() => {
    sessionContextRef.current = sessionContext;
  }, [sessionContext]);
  
  useEffect(() => {
    sessionDurationRef.current = sessionDuration;
  }, [sessionDuration]);
  
  // Update job tracking refs when state changes
  useEffect(() => {
    waitingForComprehensiveJobIdRef.current = waitingForComprehensiveJobId;
  }, [waitingForComprehensiveJobId]);
  
  useEffect(() => {
    displayedRealtimeJobIdRef.current = displayedRealtimeJobId;
  }, [displayedRealtimeJobId]);
  
  useEffect(() => {
    displayedComprehensiveJobIdRef.current = displayedComprehensiveJobId;
  }, [displayedComprehensiveJobId]);

  // Helper function to trigger both realtime and comprehensive analysis with shared ID
  const triggerPairedAnalysis = useCallback((transcriptSegment: any[], triggerSource: string) => {
    if (transcriptSegment.length === 0) return;
    
    // Increment job counter and get shared ID for both analyses
    analysisJobCounterRef.current += 1;
    const sharedJobId = analysisJobCounterRef.current;
    
    console.log(`[Session] 🔄 ${triggerSource} triggered - Job ID: ${sharedJobId}`);

    // Log "started" entries for both analyses
    addLogEntry('flash', 'realtime', 'started', `Realtime analysis started (Job ${sharedJobId})`, {
      ragTools: ['ebt-corpus', 'cbt-corpus'],
    });
    addLogEntry('pro', 'comprehensive', 'started', `Comprehensive analysis started (Job ${sharedJobId})`, {
      ragTools: ['ebt-corpus', 'cbt-corpus', 'transcript-patterns'],
    });

    // Get the most recent alert for backend deduplication (realtime only)
    const recentAlert = alertsRef.current.length > 0 ? alertsRef.current[0] : null;

    // Trigger both analyses with the same job ID
    analyzeSegmentRef.current(
      transcriptSegment,
      { ...sessionContextRef.current, is_realtime: true },
      Math.floor(sessionDurationRef.current / 60),
      recentAlert,
      sharedJobId
    );
    
    analyzeSegmentRef.current(
      transcriptSegment,
      { ...sessionContextRef.current, is_realtime: false },
      Math.floor(sessionDurationRef.current / 60),
      undefined, // no previous alert for comprehensive
      sharedJobId
    );
  }, [addLogEntry]);

  // Word-based real-time analysis trigger (simplified)
  useEffect(() => {
    if (!isRecording || transcript.length === 0) return;
    
    const lastEntry = transcript[transcript.length - 1];
    if (!lastEntry || lastEntry.is_interim) return;
    
    // Count words in the new entry
    const newWords = lastEntry.text.split(' ').filter(word => word.trim()).length;
    
    setWordsSinceLastAnalysis(prev => {
      const updatedWordCount = prev + newWords;
      
      // Trigger analysis every 30 words (~1-2 sentences) for more meaningful context
      const WORDS_PER_ANALYSIS = 30;
      const TRANSCRIPT_WINDOW_MINUTES = 5;
      
      if (updatedWordCount >= WORDS_PER_ANALYSIS) {
        // Get last 5 minutes of transcript
        const fiveMinutesAgo = new Date(Date.now() - TRANSCRIPT_WINDOW_MINUTES * 60 * 1000);
        const recentTranscript = transcript
          .filter(t => !t.is_interim && new Date(t.timestamp) > fiveMinutesAgo)
          .map(t => ({
            speaker: 'conversation',
            text: t.text,
            timestamp: t.timestamp
          }));
        
        if (recentTranscript.length > 0) {
          triggerPairedAnalysis(recentTranscript, `Auto-analysis (${updatedWordCount} words)`);
        }
        
        // Reset word count
        return 0;
      }
      
      return updatedWordCount;
    });
  }, [transcript, isRecording, triggerPairedAnalysis]);

  // Generate current date in the format "Month Day, Year"
  const getCurrentDate = () => {
    const today = new Date();
    return today.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  // Get patient name from patientId
  const getPatientName = () => {
    if (patientId) {
      const patient = mockPatients.find(p => p.id === patientId);
      return patient?.name || 'New Session';
    }
    return 'New Session';
  };

  // Determine therapy phase
  const determineTherapyPhase = (duration: number) => {
    if (duration <= 10 * 60) {
      return "Beginning (1-10 minutes)";
    } else if (duration <= 40 * 60) {
      return "Middle (10-40 minutes)";
    } else {
      return "End (40+ minutes)";
    }
  };

  // Get current alert for tab display
  const getCurrentAlert = () => {
    if (alerts.length > 0 && displayedRealtimeJobId !== null) {
      const recentAlert = alerts[0];
      return {
        title: recentAlert.title || "Current Alert",
        category: recentAlert.category || "general",
        timing: recentAlert.timing || "info"
      };
    }
    return null;
  };

  // Get current guidance for Guidance tab (realtime analysis only)
  const getCurrentGuidance = () => {
    // Show real-time alerts for Guidance tab
    if (alerts.length > 0) {
      const recentAlert = alerts[0];

      // Build immediate actions from backend immediateActions first, then fall back to recommendation
      const backendActions = recentAlert.immediateActions || [];
      const recommendationItems = Array.isArray(recentAlert.recommendation)
        ? recentAlert.recommendation
        : recentAlert.recommendation ? [recentAlert.recommendation] : [];
      const actionSources = backendActions.length > 0 ? backendActions : recommendationItems;

      const immediateActions = actionSources.map((action) => ({
        title: action,
        description: action,
        icon: 'safety' as const
      }));

      // Build contraindications from backend contraindications field
      const backendContraindications = recentAlert.contraindications || [];
      const contraindications = backendContraindications.map((contra) => ({
        title: contra,
        description: contra,
        icon: 'cognitive' as const
      }));

      return {
        title: recentAlert.title || "Current Clinical Guidance",
        time: formatDuration(sessionDuration),
        content: recentAlert.message || "Real-time guidance available.",
        immediateActions,
        contraindications
      };
    }
    
    // Default guidance when no realtime alerts available
    return {
      title: isRecording ? "Listening for guidance..." : "No guidance available",
      time: formatDuration(sessionDuration),
      content: isRecording 
        ? "Listening..."
        : "Start a session to receive real-time therapeutic guidance.",
      immediateActions: [],
      contraindications: []
    };
  };

  // Get pathway guidance for Pathway tab (comprehensive analysis only)
  const getPathwayGuidance = () => {
    // Show comprehensive results if available and job IDs match
    if (pathwayGuidance.rationale && displayedComprehensiveJobId === displayedRealtimeJobId) {
      return {
        title: "Current Clinical Guidance",
        time: formatDuration(sessionDuration),
        content: pathwayGuidance.rationale,
        immediateActions: pathwayGuidance.immediate_actions?.map(action => ({
          title: action,
          description: action,
          icon: 'safety' as const
        })) || [],
        contraindications: pathwayGuidance.contraindications?.map(contra => ({
          title: contra,
          description: contra,
          icon: 'cognitive' as const
        })) || [],
        isLive: true,
        jobId: displayedComprehensiveJobId
      };
    }
    
    // Show loading state when waiting for comprehensive results
    if (waitingForComprehensiveJobId !== null) {
      return {
        title: "Creating comprehensive therapeutic guidance...",
        time: formatDuration(sessionDuration),
        content: "Creating comprehensive therapeutic guidance...",
        immediateActions: [],
        contraindications: [],
        isLive: false,
        isLoading: true,
        jobId: waitingForComprehensiveJobId
      };
    }
    
    // Default when no analysis available yet
    return {
      title: hasReceivedComprehensiveAnalysis ? "No pathway guidance available" : "Waiting for analysis...",
      time: formatDuration(sessionDuration),
      content: hasReceivedComprehensiveAnalysis 
        ? "Start a session to receive comprehensive therapeutic guidance."
        : "Start a session to receive comprehensive therapeutic guidance.",
      immediateActions: [],
      contraindications: [],
      isLive: false,
      jobId: null
    };
  };

  // Session control functions
  const handleStartSession = async () => {
    setSessionStartTime(new Date());
    setIsRecording(true);
    setSessionType('microphone');
    setSessionSummaryClosed(false);
    setSessionSummary(null);
    setSummaryError(null);
    setPausedTime(0);
    setIsPaused(false);
    setHasReceivedComprehensiveAnalysis(false);
    setTranscript([]);
    setAlerts([]);
    
    // Reset job tracking state
    setDisplayedRealtimeJobId(null);
    setDisplayedComprehensiveJobId(null);
    setWaitingForComprehensiveJobId(null);
    setPathwayGuidance({});
    setCitations([]);
    
    // Clear chart data for new session
    setChartDataHistory([]);
    
    await startMicrophoneRecording();
  };

  const handlePauseResume = async () => {
    if (isPaused) {
      // Resume
      const now = new Date();
      if (lastPauseTime) {
        const pauseDuration = Math.floor((now.getTime() - lastPauseTime.getTime()) / 1000);
        setPausedTime(prev => prev + pauseDuration);
      }
      setIsPaused(false);
      setLastPauseTime(null);
      
      // Resume based on session type
      if (sessionType === 'microphone') {
        await startMicrophoneRecording();
      } else if (sessionType === 'audio') {
        await resumeAudioStreaming();
      } else if (sessionType === 'test') {
        resumeTestMode();
      }
    } else {
      // Pause
      setIsPaused(true);
      setLastPauseTime(new Date());
      
      // Pause based on session type
      if (sessionType === 'microphone') {
        await stopStreaming();
      } else if (sessionType === 'audio') {
        pauseAudioStreaming();
      } else if (sessionType === 'test') {
        pauseTestMode();
      }
    }
  };

  const handleStopSession = async () => {
    setIsRecording(false);
    setIsPaused(false);
    setSessionType(null);
    await stopStreaming();
    if (isTestMode) {
      stopTestMode();
    }
    if (transcript.length > 0) {
      requestSummary();
    }
  };

  const requestSummary = async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    setSessionSummaryClosed(true);
    try {
      const fullTranscript = transcript
        .filter(t => !t.is_interim)
        .map(t => ({
          speaker: 'conversation',
          text: t.text,
          timestamp: t.timestamp,
        }));
      
      const result = await generateSessionSummary(fullTranscript, sessionMetrics);

      if (result.summary) {
        setSessionSummary(result.summary);
        setShowSessionSummary(true);
      } else {
        throw new Error('Invalid summary response');
      }
    } catch (err) {
      console.error('Error generating summary:', err);
      setSummaryError('Failed to generate session summary. Please try again.');
    } finally {
      setSummaryLoading(false);
    }
  };

  // Shared function to start interval-based transcript playback
  const startTranscriptPlayback = (data: TestTranscriptEntry[]) => {
    setIsTestMode(true);
    setIsRecording(true);
    setSessionType('test');
    setSessionStartTime(new Date());
    setTranscript([]);
    setPausedTime(0);
    setIsPaused(false);
    setHasReceivedComprehensiveAnalysis(false);

    // Reset job tracking state
    setDisplayedRealtimeJobId(null);
    setDisplayedComprehensiveJobId(null);
    setWaitingForComprehensiveJobId(null);
    setPathwayGuidance({});
    setCitations([]);

    // Clear chart data - will be populated by real analysis responses
    setChartDataHistory([]);

    // Reset session metrics - will be populated by analysis
    setSessionMetrics({
      engagement_level: 0.0,
      therapeutic_alliance: 'unknown',
      techniques_detected: [],
      emotional_state: 'unknown',
      arousal_level: 'unknown',
      phase_appropriate: false,
    });

    activeTranscriptDataRef.current = data;

    let currentIndex = 0;
    testIntervalRef.current = setInterval(() => {
        if (currentIndex >= data.length) {
          if (testIntervalRef.current) {
            clearInterval(testIntervalRef.current);
            testIntervalRef.current = null;
          }
          setIsTestMode(false);
          setIsRecording(false);
          setSessionType(null);
          // Auto-trigger summary when script finishes
          requestSummary();
          return;
        }

        const entry = data[currentIndex];
        const formattedEntry = {
          text: entry.speaker ? `${entry.speaker}: ${entry.text}` : entry.text,
          timestamp: new Date().toISOString(),
          is_interim: false,
        };

        setTranscript(prev => [...prev, formattedEntry]);

        if (!transcriptOpen) {
          setNewTranscriptCount(prev => prev + 1);
        }

        currentIndex++;
    }, 2000);
  };

  // Test mode functions
  const loadTestTranscript = () => {
    startTranscriptPlayback(testTranscriptData);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Reset file input so same file can be re-selected
    event.target.value = '';

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const parsed = JSON.parse(content);

        if (!Array.isArray(parsed)) {
          setError('Invalid file: expected a JSON array of transcript entries.');
          return;
        }
        if (parsed.length === 0) {
          setError('Transcript file is empty.');
          return;
        }

        // Validate structure
        const isValid = parsed.every((entry: any) =>
          typeof entry === 'object' && entry !== null &&
          typeof entry.speaker === 'string' && typeof entry.text === 'string'
        );
        if (!isValid) {
          setError('Invalid format: each entry must have "speaker" and "text" string fields.');
          return;
        }

        // Map to TestTranscriptEntry format
        const transcriptData: TestTranscriptEntry[] = parsed.map((entry: any) => ({
          text: entry.text,
          timestamp: new Date().toISOString(),
          is_interim: false as const,
          speaker: entry.speaker as 'THERAPIST' | 'PATIENT',
        }));

        setError(null);
        startTranscriptPlayback(transcriptData);
      } catch {
        setError('Failed to parse JSON file. Please check the file format.');
      }
    };
    reader.onerror = () => {
      setError('Failed to read the file.');
    };
    reader.readAsText(file);
  };

  const pauseTestMode = () => {
    if (testIntervalRef.current) {
      clearInterval(testIntervalRef.current);
      testIntervalRef.current = null;
    }
  };

  const resumeTestMode = () => {
    if (isTestMode && !testIntervalRef.current) {
      const data = activeTranscriptDataRef.current;
      // Resume from where we left off
      const currentTranscriptLength = transcript.filter(t => !t.is_interim).length;
      let currentIndex = currentTranscriptLength;

      testIntervalRef.current = setInterval(() => {
        if (currentIndex >= data.length) {
          if (testIntervalRef.current) {
            clearInterval(testIntervalRef.current);
            testIntervalRef.current = null;
          }
          setIsTestMode(false);
          setIsRecording(false);
          setSessionType(null);
          requestSummary();
          return;
        }

        const entry = data[currentIndex];
        const formattedEntry = {
          text: entry.speaker ? `${entry.speaker}: ${entry.text}` : entry.text,
          timestamp: new Date().toISOString(),
          is_interim: false,
        };

        setTranscript(prev => [...prev, formattedEntry]);

        if (!transcriptOpen) {
          setNewTranscriptCount(prev => prev + 1);
        }

        currentIndex++;
      }, 2000);
    }
  };

  const stopTestMode = () => {
    if (testIntervalRef.current) {
      clearInterval(testIntervalRef.current);
      testIntervalRef.current = null;
    }
    setIsTestMode(false);
    setIsRecording(false);
  };

  const loadExampleAudio = async () => {
    setIsRecording(true);
    setSessionType('audio');
    setSessionStartTime(new Date());
    setTranscript([]);
    setSessionSummaryClosed(false);
    setSessionSummary(null);
    setSummaryError(null);
    setPausedTime(0);
    setIsPaused(false);
    setHasReceivedComprehensiveAnalysis(false);
    
    // Reset job tracking state
    setDisplayedRealtimeJobId(null);
    setDisplayedComprehensiveJobId(null);
    setWaitingForComprehensiveJobId(null);
    setPathwayGuidance({});
    setCitations([]);

    // Clear chart data - will be populated by real analysis responses
    setChartDataHistory([]);

    // Reset session metrics - will be populated by analysis
    setSessionMetrics({
      engagement_level: 0.0,
      therapeutic_alliance: 'unknown',
      techniques_detected: [],
      emotional_state: 'unknown',
      arousal_level: 'unknown',
      phase_appropriate: false,
    });

    // Start streaming the example audio file
    await startAudioFileStreaming('/audio/suny-good-audio.mp3');
  };

  const handleActionClick = (action: any, isContra: boolean) => {
    setSelectedAction(action);
    setSelectedCitation(null); // Clear citation if action is selected
    setIsContraindication(isContra);
  };

  const handleCitationClick = (citation: any) => {
    setSelectedCitation(citation);
    setSelectedAction(null); // Clear action if citation is selected
  };

  const handleClosePanel = () => {
    setSelectedAction(null);
    setSelectedCitation(null);
  };

  const handleCitationModalClick = (citation: Citation) => {
    setSelectedCitationModal(citation);
    setCitationModalOpen(true);
  };

  const getEmotionalStateColor = (state: string) => {
    switch (state) {
      case 'calm': return '#128937';
      case 'anxious': return '#f59e0b';
      case 'distressed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getArousalColor = (level: string) => {
    switch (level) {
      case 'low': return '#3b82f6';      // Blue - low arousal
      case 'moderate': return '#10b981'; // Green - optimal
      case 'high': return '#f59e0b';     // Amber - elevated
      case 'elevated': return '#ef4444'; // Red - very high
      default: return '#6b7280';         // Gray - unknown
    }
  };

  // Get alert category icon
  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'safety':
        return <Shield sx={{ fontSize: 20, color: '#dc2626' }} />;
      case 'technique':
        return <Psychology sx={{ fontSize: 20, color: '#c05a01' }} />;
      case 'pathway_change':
        return <SwapHoriz sx={{ fontSize: 20, color: '#f59e0b' }} />;
      case 'engagement':
        return <Lightbulb sx={{ fontSize: 20, color: '#10b981' }} />;
      case 'process':
        return <Assessment sx={{ fontSize: 20, color: '#6366f1' }} />;
      default:
        return <Build sx={{ fontSize: 20, color: '#6b7280' }} />;
    }
  };

  // Helper function to ensure recommendations are formatted as bullet points
  const normalizeRecommendationFormat = (recommendation: string): string => {
    if (!recommendation) return recommendation;
    
    // If it already contains markdown bullet points, return as-is
    if (recommendation.includes('- ') || recommendation.includes('* ')) {
      return recommendation;
    }
    
    // Split by periods or newlines to create separate bullet points
    const lines = recommendation
      .split(/[.\n]/)
      .map(line => line.trim())
      .filter(line => line.length > 0);
    
    // If we only have one line, return as-is (might be a single sentence)
    if (lines.length <= 1) {
      return recommendation;
    }
    
    // Convert to markdown bullet points
    return lines.map(line => `- ${line}`).join('\n');
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming();
      if (testIntervalRef.current) {
        clearInterval(testIntervalRef.current);
      }
    };
  }, [stopStreaming]);

  return (
    <Box sx={{ 
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      maxHeight: '100vh',
      background: '#f0f4f9',
      p: 1.5,
      overflow: 'hidden',
    }}>
      {/* Main Container */}
      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
        backgroundColor: 'white',
        borderRadius: '8px',
        overflow: 'hidden',
      }}>
        {/* Main Content Area */}
        <Box sx={{
          display: 'flex',
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          position: 'relative',
        }}>
          <ActionDetailsPanel
            action={selectedAction}
            citation={selectedCitation}
            onClose={handleClosePanel}
            isContraindication={isContraindication}
          />
          {/* Sidebar */}
          <Box sx={{
            width: 351,
            display: 'flex',
            transform: (selectedAction || selectedCitation) ? 'translateX(-100%)' : 'translateX(0)',
            transition: 'transform 0.3s ease-in-out',
            flexDirection: 'column',
            gap: 2,
            p: 2,
            minHeight: 0,
            overflow: 'hidden',
          }}>
            {/* Title Section */}
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
                {onNavigateBack && (
                  <Button
                    startIcon={<ArrowBack />}
                    onClick={onNavigateBack}
                    sx={{
                      color: '#0b57d0',
                      textTransform: 'none',
                      fontSize: '14px',
                      fontWeight: 500,
                      minWidth: 'auto',
                      px: 1,
                      py: 0.5,
                      '&:hover': {
                        backgroundColor: 'rgba(11, 87, 208, 0.04)',
                      },
                    }}
                  >
                  </Button>
                )}
                <Typography variant="h6" sx={{
                  fontSize: '20px',
                  fontWeight: 600,
                  color: '#1f1f1f',
                }}>
                  {getPatientName()}
                </Typography>
              </Box>
              <Typography variant="body2" sx={{
                fontSize: '13px',
                color: '#444746',
                mb: 0.5,
              }}>
                {getCurrentDate()}
              </Typography>
              <BackendStatusIndicator />
            </Box>

            {/* Navigation Menu */}
            <Box>
            {[
              { key: 'guidance', label: 'Guidance', icon: <Explore sx={{ fontSize: 24, color: '#444746' }} /> },
              { key: 'pathway', label: 'Pathway', icon: <Route sx={{ fontSize: 24, color: '#444746' }} /> },
              { key: 'alternatives', label: 'Alternatives', icon: <CallSplit sx={{ fontSize: 24, color: '#444746' }} /> },
            ].map((item) => (
                <Box
                  key={item.key}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    height: 44,
                    px: 1.5,
                    py: 0.5,
                    cursor: 'pointer',
                    backgroundColor: activeTab === item.key ? 'rgba(0, 0, 0, 0.04)' : 'transparent',
                    '&:hover': {
                      backgroundColor: 'rgba(0, 0, 0, 0.04)',
                    },
                    borderBottom: item.key !== 'alternatives' ? '1px solid rgba(196, 199, 197, 0.3)' : 'none',
                  }}
                  onClick={() => setActiveTab(item.key as any)}
                >
                  <Box sx={{ mr: 1.5, width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {activeTab === item.key ? item.icon : null}
                  </Box>
                  <Typography variant="body1" sx={{ fontSize: '18px', color: '#1f1f1f' }}>
                    {item.label}
                  </Typography>
                </Box>
              ))}
            </Box>

            {/* LLM Activity Log */}
            <ActivityLog
              entries={activityLogEntries}
              onClear={() => setActivityLogEntries([])}
            />
          </Box>

          {/* Main Content */}
          <Box sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            p: 2,
            gap: 1.5,
            overflow: 'auto',
            minHeight: 0,
          }}>
            {activeTab === 'guidance' && (
              <GuidanceTab
                currentGuidance={getCurrentGuidance()}
                alerts={alerts}
                transcript={transcript}
                pathwayGuidance={pathwayGuidance}
                onActionClick={handleActionClick}
                sessionMetrics={sessionMetrics}
              />
            )}
            {activeTab === 'evidence' && (
              <EvidenceTab
                currentAlert={alerts.length > 0 ? alerts[0] : null}
                sessionDuration={sessionDuration}
              />
            )}
            {activeTab === 'pathway' && (
              <PathwayTab
                onCitationClick={handleCitationClick}
                onActionClick={handleActionClick}
                currentGuidance={getPathwayGuidance()}
                citations={citations}
                techniques={sessionMetrics.techniques_detected}
                currentAlert={getCurrentAlert()}
                pathwayIndicators={pathwayIndicators}
              />
            )}
            {activeTab === 'alternatives' && (
              <AlternativesTab 
                alternativePathways={pathwayGuidance.alternative_pathways}
                citations={citations}
                onCitationClick={handleCitationClick}
                hasReceivedComprehensiveAnalysis={hasReceivedComprehensiveAnalysis}
                waitingForComprehensiveJobId={waitingForComprehensiveJobId}
                displayedComprehensiveJobId={displayedComprehensiveJobId}
                displayedRealtimeJobId={displayedRealtimeJobId}
                currentAlert={getCurrentAlert()}
              />
            )}
          </Box>
        </Box>

        {/* Timeline Section */}
        <Box sx={{
          backgroundColor: 'white',
          px: 2,
          py: 1,
          borderTop: '1px solid #f0f4f9',
          flexShrink: 0,
        }}>
          {/* Chart Grid */}
          <Box sx={{ position: 'relative', mb: 1 }}>
            <Box sx={{
              backgroundColor: 'white',
              border: '1px solid #e9ebf1',
              borderRadius: 1,
              position: 'relative',
              py: 1,
              px: 0.5,
            }}>
              <SessionLineChart
                duration={sessionDuration}
                chartData={chartDataHistory}
              />
            </Box>

            {/* Dynamic event markers from actual session alerts */}
            {alerts.length > 0 && sessionDuration > 0 && alerts
              .filter(a => a.sessionTime !== undefined)
              .slice(0, 8) // Show up to 8 markers
              .map((alert, idx) => {
                // Position marker proportionally along the timeline
                const position = Math.max(5, Math.min(95, ((alert.sessionTime || 0) / sessionDuration) * 100));
                return (
                  <Tooltip key={idx} title={`${alert.title} (${alert.category})`}>
                    <IconButton
                      onClick={() => setSelectedAlertIndex(idx)}
                      sx={{
                        position: 'absolute',
                        bottom: -10,
                        left: `${position}%`,
                        transform: 'translateX(-50%)',
                        p: 0.5,
                      }}
                    >
                      {getCategoryIcon(alert.category)}
                    </IconButton>
                  </Tooltip>
                );
              })
            }
          </Box>

        </Box>

        {/* Session Header with KPIs - Now at Bottom */}
        <Box sx={{
          backgroundColor: 'white',
          borderTop: '1px solid #f0f4f9',
          borderRadius: '0 0 8px 8px',
          flexShrink: 0,
        }}>
          {/* Pathway Header */}
          <Box sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            py: 0.5,
            borderBottom: '1px solid #f0f4f9',
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Timeline sx={{ fontSize: 20, color: '#444746' }} />
              <Typography variant="h6" sx={{ fontWeight: 600, color: '#1f1f1f', fontSize: '15px' }}>
                {sessionContext.current_approach || 'Cognitive Behavioral Therapy'}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              {/* Dynamic technique chips from analysis */}
              {sessionMetrics.techniques_detected.length > 0 ? (
                sessionMetrics.techniques_detected.slice(0, 3).map((technique, idx) => (
                  <Chip
                    key={idx}
                    icon={<Check sx={{ fontSize: 18, color: '#0b57d0' }} />}
                    label={technique}
                    size="small"
                    sx={{
                      backgroundColor: 'transparent',
                      border: '1px solid #c4c7c5',
                      borderRadius: '8px',
                      '& .MuiChip-icon': { color: '#0b57d0' },
                      '& .MuiChip-label': {
                        fontSize: '12px',
                        fontWeight: 500,
                        color: '#0b57d0',
                      },
                    }}
                  />
                ))
              ) : (
                <Chip
                  label="Awaiting analysis..."
                  size="small"
                  sx={{
                    backgroundColor: 'transparent',
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    '& .MuiChip-label': {
                      fontSize: '12px',
                      fontWeight: 500,
                      color: '#9e9e9e',
                      fontStyle: 'italic',
                    },
                  }}
                />
              )}
              {/* Dynamic effectiveness chip from pathway analysis */}
              {(() => {
                const eff = pathwayIndicators.current_approach_effectiveness;
                const effConfig = {
                  effective: { bg: '#ddf8d8', border: '#beefbb', color: '#128937', label: 'Effective' },
                  struggling: { bg: '#fef3cd', border: '#fde68a', color: '#92400e', label: 'Struggling' },
                  ineffective: { bg: '#fee2e2', border: '#fca5a5', color: '#b91c1c', label: 'Ineffective' },
                  unknown: { bg: '#f3f4f6', border: '#e0e0e0', color: '#9e9e9e', label: 'Assessing...' },
                }[eff] || { bg: '#f3f4f6', border: '#e0e0e0', color: '#9e9e9e', label: 'Assessing...' };
                return (
                  <Chip
                    icon={eff !== 'unknown' ? <Check sx={{ fontSize: 18, color: effConfig.color }} /> : undefined}
                    label={effConfig.label}
                    size="small"
                    sx={{
                      backgroundColor: effConfig.bg,
                      border: `1px solid ${effConfig.border}`,
                      borderRadius: '8px',
                      '& .MuiChip-icon': { color: effConfig.color },
                      '& .MuiChip-label': {
                        fontSize: '12px',
                        fontWeight: 500,
                        color: effConfig.color,
                      },
                    }}
                  />
                );
              })()}
            </Box>
          </Box>

          {/* Session Metrics Row */}
          <Box sx={{ 
            display: 'flex',
            '& > *:not(:first-of-type)': { flex: 1 },
          }}>
            {/* Session ID / Transcript Button / Test Buttons */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              px: 1,
              py: 1,
              borderRight: '1px solid #f0f4f9',
              minWidth: isRecording ? 100 : 180,
              flexShrink: 0,
            }}>
              {isRecording ? (
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<Chat sx={{ fontSize: 16 }} />}
                  onClick={() => {
                    setTranscriptOpen(!transcriptOpen);
                    if (!transcriptOpen) {
                      setNewTranscriptCount(0);
                    }
                  }}
                  sx={{
                    borderColor: '#0b57d0',
                    color: '#0b57d0',
                    fontSize: '14px',
                    fontWeight: 500,
                    borderRadius: '4px',
                    px: 1,
                    py: 0.25,
                    minWidth: 'auto',
                    position: 'relative',
                    '& .MuiButton-startIcon': {
                      marginRight: 0.5,
                      marginLeft: 0,
                    },
                    '&:hover': {
                      borderColor: '#00639b',
                      backgroundColor: 'rgba(11, 87, 208, 0.04)',
                    },
                  }}
                >
                  Transcript
                  {newTranscriptCount > 0 && (
                    <Box
                      sx={{
                        position: 'absolute',
                        top: -4,
                        right: -4,
                        backgroundColor: '#ef4444',
                        color: 'white',
                        borderRadius: '50%',
                        minWidth: 14,
                        height: 14,
                        fontSize: '9px',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        px: 0.5,
                      }}
                    >
                      {newTranscriptCount > 99 ? '99+' : newTranscriptCount}
                    </Box>
                  )}
                </Button>
              ) : !isTestMode ? (
                <Box sx={{
                  display: 'flex',
                  gap: 0.5,
                  flexDirection: 'column',
                  alignItems: 'center',
                }}>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<VolumeUp />}
                    onClick={loadExampleAudio}
                    sx={{
                      borderColor: '#6366f1',
                      color: '#6366f1',
                      '&:hover': {
                        borderColor: '#4f46e5',
                        backgroundColor: 'rgba(99, 102, 241, 0.04)',
                      },
                      fontWeight: 600,
                      borderRadius: '12px',
                      px: 1.5,
                      py: 0.25,
                      fontSize: '11px',
                      minWidth: 'auto',
                    }}
                  >
                    Example Audio
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={loadTestTranscript}
                    sx={{
                      borderColor: '#0b57d0',
                      color: '#0b57d0',
                      '&:hover': {
                        borderColor: '#00639b',
                        backgroundColor: 'rgba(11, 87, 208, 0.04)',
                      },
                      fontWeight: 600,
                      borderRadius: '12px',
                      px: 1.5,
                      py: 0.25,
                      fontSize: '11px',
                      minWidth: 'auto',
                    }}
                  >
                    Test Transcript
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<UploadFile />}
                    onClick={() => fileInputRef.current?.click()}
                    sx={{
                      borderColor: '#0d9488',
                      color: '#0d9488',
                      '&:hover': {
                        borderColor: '#0f766e',
                        backgroundColor: 'rgba(13, 148, 136, 0.04)',
                      },
                      fontWeight: 600,
                      borderRadius: '12px',
                      px: 1.5,
                      py: 0.25,
                      fontSize: '11px',
                      minWidth: 'auto',
                    }}
                  >
                    Upload Script
                  </Button>
                  <input
                    type="file"
                    accept=".json"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                  />
                </Box>
              ) : (
                <Typography variant="h6" sx={{ fontWeight: 500, fontSize: '24px', color: '#1e1e1e' }}>
                  {sessionId}
                </Typography>
              )}
            </Box>

            {/* Emotional State */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 0.75,
              borderRight: '1px solid #f0f4f9',
              minWidth: 90,
              overflow: 'hidden',
            }}>
              <Box sx={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: getEmotionalStateColor(sessionMetrics.emotional_state),
                flexShrink: 0,
              }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '9px',
                  color: '#5f6368',
                  textTransform: 'uppercase',
                  letterSpacing: '0.3px',
                  lineHeight: 1.2,
                  whiteSpace: 'nowrap',
                }}>
                  Emotional
                </Typography>
                <Typography sx={{ fontWeight: 600, fontSize: '12px', color: '#1f1f1f', textTransform: 'capitalize', lineHeight: 1.3, whiteSpace: 'nowrap' }}>
                  {sessionMetrics.emotional_state}
                </Typography>
              </Box>
            </Box>

            {/* Engagement Level */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 0.75,
              borderRight: '1px solid #f0f4f9',
              minWidth: 90,
              overflow: 'hidden',
            }}>
              <Box sx={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: '#0b57d0',
                flexShrink: 0,
              }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '9px',
                  color: '#5f6368',
                  textTransform: 'uppercase',
                  letterSpacing: '0.3px',
                  lineHeight: 1.2,
                  whiteSpace: 'nowrap',
                }}>
                  Engagement
                </Typography>
                <Typography sx={{ fontWeight: 600, fontSize: '12px', color: '#1f1f1f', lineHeight: 1.3, whiteSpace: 'nowrap' }}>
                  {sessionMetrics.engagement_level === 0 ? '—' : `${Math.round(sessionMetrics.engagement_level * 100)}%`}
                </Typography>
              </Box>
            </Box>

            {/* Therapeutic Alliance */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 0.75,
              borderRight: '1px solid #f0f4f9',
              minWidth: 90,
              overflow: 'hidden',
            }}>
              <Box sx={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: '#9254ea',
                flexShrink: 0,
              }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '9px',
                  color: '#5f6368',
                  textTransform: 'uppercase',
                  letterSpacing: '0.3px',
                  lineHeight: 1.2,
                  whiteSpace: 'nowrap',
                }}>
                  Alliance
                </Typography>
                <Typography sx={{ fontWeight: 600, fontSize: '12px', color: '#1f1f1f', textTransform: 'capitalize', lineHeight: 1.3, whiteSpace: 'nowrap' }}>
                  {sessionMetrics.therapeutic_alliance}
                </Typography>
              </Box>
            </Box>

            {/* Arousal Level */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 0.75,
              borderRight: '1px solid #f0f4f9',
              minWidth: 90,
              overflow: 'hidden',
            }}>
              <Box sx={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: getArousalColor(sessionMetrics.arousal_level),
                flexShrink: 0,
              }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '9px',
                  color: '#5f6368',
                  textTransform: 'uppercase',
                  letterSpacing: '0.3px',
                  lineHeight: 1.2,
                  whiteSpace: 'nowrap',
                }}>
                  Arousal
                </Typography>
                <Typography sx={{ fontWeight: 600, fontSize: '12px', color: '#1f1f1f', textTransform: 'capitalize', lineHeight: 1.3, whiteSpace: 'nowrap' }}>
                  {sessionMetrics.arousal_level}
                </Typography>
              </Box>
            </Box>

            {/* Phase Indicator */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 0.75,
              borderRight: '1px solid #f0f4f9',
              minWidth: 110,
              overflow: 'hidden',
            }}>
              <Check sx={{ fontSize: 16, color: sessionMetrics.phase_appropriate ? '#128937' : '#f59e0b' }} />
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{
                  fontSize: '9px',
                  color: '#5f6368',
                  textTransform: 'uppercase',
                  letterSpacing: '0.3px',
                  lineHeight: 1.2,
                }}>
                  {determineTherapyPhase(sessionDuration)}
                </Typography>
                <Typography sx={{ fontWeight: 600, fontSize: '12px', color: sessionMetrics.phase_appropriate ? '#128937' : '#f59e0b', lineHeight: 1.3, whiteSpace: 'nowrap' }}>
                  {sessionMetrics.phase_appropriate ? 'Phase-appropriate' : 'Assessing...'}
                </Typography>
              </Box>
            </Box>

            {/* Timer and Controls */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 1.5,
              px: 2,
              py: 0.75,
            }}>
              <Typography variant="h6" sx={{ fontWeight: 400, fontSize: '22px', color: '#444746' }}>
                {formatDuration(sessionDuration)}
              </Typography>
              {!isRecording ? (
                <Button
                  variant="contained"
                  startIcon={<Mic />}
                  onClick={handleStartSession}
                  sx={{ 
                    background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                    color: 'white',
                    '&:hover': {
                      background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
                    },
                  }}
                >
                  Start Session
                </Button>
              ) : (
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="contained"
                    startIcon={isPaused ? <PlayArrow /> : <Pause />}
                    onClick={handlePauseResume}
                    sx={{ 
                      background: isPaused 
                        ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                        : 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                      color: 'white',
                      '&:hover': { 
                        background: isPaused
                          ? 'linear-gradient(135deg, #059669 0%, #10b981 100%)'
                          : 'linear-gradient(135deg, #d97706 0%, #f59e0b 100%)',
                      },
                    }}
                  >
                    {isPaused ? 'Resume' : 'Pause'}
                  </Button>
                  <IconButton
                    onClick={handleStopSession}
                    sx={{
                      backgroundColor: '#f9dedc',
                      color: '#8c1d18',
                      width: 40,
                      height: 40,
                      '&:hover': {
                        backgroundColor: '#f5c6c6',
                      },
                    }}
                  >
                    <Stop />
                  </IconButton>
                </Box>
              )}
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Floating Action Buttons */}
      <Box sx={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1201, display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-end' }}>
        {/* Reopen Session Summary Button */}
        {sessionSummaryClosed && !showSessionSummary && (
          <Fab
            color="secondary"
            variant="extended"
            aria-label="reopen session summary"
            onClick={() => setShowSessionSummary(true)}
            sx={{
              background: 'linear-gradient(135deg, #673ab7 0%, #512da8 100%)',
              color: 'white',
              '&:hover': {
                background: 'linear-gradient(135deg, #512da8 0%, #673ab7 100%)',
                transform: 'scale(1.05)',
              },
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              boxShadow: '0 8px 20px -4px rgba(103, 58, 183, 0.35)',
            }}
          >
            <Article sx={{ mr: 1 }} />
            Summary
          </Fab>
        )}
      </Box>


      {/* Left Sidebar - Transcript */}
      <Drawer
        anchor="left"
        open={transcriptOpen}
        onClose={() => setTranscriptOpen(false)}
        sx={{
          '& .MuiDrawer-paper': {
            width: isDesktop ? 400 : 350,
            p: 3,
            pt: 10,
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.75) 0%, rgba(248, 250, 252, 0.85) 100%)',
            backdropFilter: 'blur(24px) saturate(180%)',
            WebkitBackdropFilter: 'blur(24px) saturate(180%)',
            boxShadow: '8px 0 32px -4px rgba(0, 0, 0, 0.12)',
            borderRight: '1px solid rgba(255, 255, 255, 0.5)',
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.2) 0%, transparent 100%)',
              pointerEvents: 'none',
            },
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
          <Typography 
            variant="h5" 
            sx={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: 1.5,
              color: 'var(--primary)',
              fontWeight: 600,
            }}
          >
            <Article sx={{ 
              fontSize: 28,
              background: 'linear-gradient(135deg, #0b57d0 0%, #00639b 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }} />
            Live Transcript
          </Typography>
          <IconButton 
            onClick={() => setTranscriptOpen(false)}
            sx={{ 
              color: 'var(--on-surface-variant)',
              '&:hover': {
                background: 'rgba(0, 0, 0, 0.04)',
              },
            }}
          >
            <Close />
          </IconButton>
        </Box>
        
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          <TranscriptDisplay transcript={transcript} />
        </Box>
      </Drawer>

      {/* Error Display */}
      {error && (
        <Box sx={{ position: 'fixed', top: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 1300 }}>
          <MuiAlert severity="error" onClose={() => setError(null)}>
            {error}
          </MuiAlert>
        </Box>
      )}

      {/* Session Summary Modal */}
      <SessionSummaryModal
        open={showSessionSummary}
        onClose={() => setShowSessionSummary(false)}
        summary={sessionSummary}
        loading={summaryLoading}
        error={summaryError}
        onRetry={requestSummary}
        sessionId={sessionId}
      />

      <RationaleModal
        open={showRationaleModal}
        onClose={() => setShowRationaleModal(false)}
        rationale={pathwayGuidance.rationale}
        immediateActions={pathwayGuidance.immediate_actions}
        contraindications={pathwayGuidance.contraindications}
        citations={citations}
        onCitationClick={handleCitationModalClick}
      />

      <CitationModal
        open={citationModalOpen}
        onClose={() => {
          setCitationModalOpen(false);
          setSelectedCitationModal(null);
        }}
        citation={selectedCitationModal}
      />

      {/* Clinician Notes Panel - sticky at bottom */}
      <TherapistNotesPanel sessionInstanceId={sessionInstanceId} />

    </Box>
  );
};

export default NewTherSession;
