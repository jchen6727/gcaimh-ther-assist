/**
 * Chart Data Utilities
 *
 * Provides the ChartDataPoint interface and utility functions for
 * converting backend analysis responses into chart-ready data.
 */

import { SessionMetrics, PathwayIndicators } from '../types/types';

/**
 * Raw chart data point collected from comprehensive analysis responses.
 */
export interface ChartDataPoint {
  timestamp: string;
  sessionTimeSeconds: number;
  engagement_level: number;          // 0-100 scale
  therapeutic_alliance_score: number; // 0-100 scale
  emotional_state_score: number;      // 0-100 scale
  techniques_count: number;
  effectiveness_score: number;        // 0-100 scale
  change_urgency_level: number;       // 0-100 scale
  jobId: number;
}

/**
 * Formatted data point for Recharts rendering.
 */
interface FormattedChartPoint {
  timeDisplay: string;
  engagement: number;
  alliance: number;
  isInterpolated: boolean;
}

/**
 * Map therapeutic_alliance string to a 0-100 numeric score.
 */
const allianceToScore = (alliance: string): number => {
  switch (alliance) {
    case 'strong': return 90;
    case 'moderate': return 60;
    case 'weak': return 30;
    default: return 50;
  }
};

/**
 * Map emotional_state string to a 0-100 numeric score.
 * Higher = calmer/more positive.
 */
const emotionalStateToScore = (state: string): number => {
  switch (state) {
    case 'calm': return 85;
    case 'engaged': return 75;
    case 'anxious': return 45;
    case 'distressed': return 25;
    case 'dissociated': return 15;
    default: return 50;
  }
};

/**
 * Map current_approach_effectiveness to a 0-100 numeric score.
 */
const effectivenessToScore = (effectiveness: string): number => {
  switch (effectiveness) {
    case 'effective': return 85;
    case 'struggling': return 50;
    case 'ineffective': return 20;
    default: return 50;
  }
};

/**
 * Map change_urgency to a 0-100 numeric score.
 */
const urgencyToScore = (urgency: string): number => {
  switch (urgency) {
    case 'none': return 10;
    case 'monitor': return 35;
    case 'consider': return 60;
    case 'recommended': return 85;
    default: return 25;
  }
};

/**
 * Create a ChartDataPoint from backend comprehensive analysis response data.
 *
 * @param sessionMetrics - session_metrics from the analysis response
 * @param pathwayIndicators - pathway_indicators from the analysis response
 * @param sessionDurationSeconds - current session duration in seconds
 * @param jobId - the job ID for this analysis cycle
 */
export const createChartDataPoint = (
  sessionMetrics: SessionMetrics,
  pathwayIndicators: PathwayIndicators,
  sessionDurationSeconds: number,
  jobId: number
): ChartDataPoint => {
  return {
    timestamp: new Date().toISOString(),
    sessionTimeSeconds: sessionDurationSeconds,
    engagement_level: Math.round(sessionMetrics.engagement_level * 100),
    therapeutic_alliance_score: allianceToScore(sessionMetrics.therapeutic_alliance),
    emotional_state_score: emotionalStateToScore(sessionMetrics.emotional_state),
    techniques_count: sessionMetrics.techniques_detected?.length ?? 0,
    effectiveness_score: effectivenessToScore(pathwayIndicators.current_approach_effectiveness),
    change_urgency_level: urgencyToScore(pathwayIndicators.change_urgency),
    jobId,
  };
};

/**
 * Format raw ChartDataPoint array into Recharts-compatible data.
 * Converts sessionTimeSeconds into human-readable time labels and
 * maps fields to the keys expected by SessionLineChart.
 */
export const formatDataForChart = (dataPoints: ChartDataPoint[]): FormattedChartPoint[] => {
  return dataPoints.map(point => {
    const totalSeconds = point.sessionTimeSeconds;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    const timeDisplay = seconds > 0 ? `${minutes}:${String(seconds).padStart(2, '0')}` : `${minutes} min`;

    return {
      timeDisplay,
      engagement: point.engagement_level,
      alliance: point.therapeutic_alliance_score,
      isInterpolated: false,
    };
  });
};

/**
 * Prune chart data to keep at most maxPoints entries.
 * Keeps the first and last points, and evenly samples the rest.
 */
export const pruneChartData = (data: ChartDataPoint[], maxPoints: number): ChartDataPoint[] => {
  if (data.length <= maxPoints) {
    return data;
  }

  const result: ChartDataPoint[] = [data[0]];
  const step = (data.length - 1) / (maxPoints - 1);

  for (let i = 1; i < maxPoints - 1; i++) {
    const index = Math.round(i * step);
    result.push(data[index]);
  }

  result.push(data[data.length - 1]);
  return result;
};
