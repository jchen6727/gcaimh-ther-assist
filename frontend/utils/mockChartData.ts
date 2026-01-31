/**
 * Deterministic Mock Chart Data Generator
 * Generates consistent, reproducible chart data for the Session Metrics Time Series
 * without any randomness or backend dependency.
 */

import { ChartDataPoint } from './chartDataUtils';

/**
 * Generate deterministic mock chart data for a therapy session.
 * The data simulates a realistic session progression with:
 * - Engagement Level (0-100): Patient's engagement throughout the session
 * - Therapeutic Alliance (0-100): Quality of therapist-patient relationship
 * - Emotional State (0-100): Patient's emotional wellness (higher = calmer)
 *
 * @param durationMinutes - Total session duration in minutes (default: 45)
 * @param intervalMinutes - Time between data points in minutes (default: 5)
 * @returns Array of ChartDataPoint objects
 */
export const generateMockChartData = (
  durationMinutes: number = 45,
  intervalMinutes: number = 5
): ChartDataPoint[] => {
  const dataPoints: ChartDataPoint[] = [];

  // Deterministic progression patterns for a typical therapy session
  // These values tell a realistic story of a session
  const sessionProgressions = [
    // Start: Building rapport, moderate engagement, patient slightly anxious
    { engagement: 55, alliance: 50, emotional: 45, effectiveness: 50, urgency: 30, techniques: 1 },
    // 5 min: Warming up, alliance building
    { engagement: 62, alliance: 58, emotional: 48, effectiveness: 55, urgency: 25, techniques: 2 },
    // 10 min: Getting into issues, engagement increases
    { engagement: 70, alliance: 65, emotional: 42, effectiveness: 60, urgency: 35, techniques: 3 },
    // 15 min: Deep work begins, emotional dip as issues surface
    { engagement: 78, alliance: 72, emotional: 38, effectiveness: 65, urgency: 45, techniques: 5 },
    // 20 min: Breakthrough moment, alliance strengthens
    { engagement: 85, alliance: 80, emotional: 52, effectiveness: 75, urgency: 40, techniques: 7 },
    // 25 min: Processing insights
    { engagement: 82, alliance: 85, emotional: 58, effectiveness: 80, urgency: 30, techniques: 9 },
    // 30 min: Integration phase
    { engagement: 80, alliance: 88, emotional: 65, effectiveness: 85, urgency: 25, techniques: 11 },
    // 35 min: Consolidation, emotional regulation improving
    { engagement: 75, alliance: 90, emotional: 72, effectiveness: 88, urgency: 20, techniques: 13 },
    // 40 min: Wrapping up, homework discussion
    { engagement: 70, alliance: 92, emotional: 78, effectiveness: 90, urgency: 15, techniques: 15 },
    // 45 min: Session end, patient calmer than start
    { engagement: 65, alliance: 90, emotional: 82, effectiveness: 92, urgency: 10, techniques: 16 },
  ];

  const totalPoints = Math.ceil(durationMinutes / intervalMinutes) + 1;

  for (let i = 0; i < totalPoints && i < sessionProgressions.length; i++) {
    const timeInSeconds = i * intervalMinutes * 60;
    const progression = sessionProgressions[i];

    dataPoints.push({
      timestamp: new Date(Date.now() - (durationMinutes * 60 - timeInSeconds) * 1000).toISOString(),
      sessionTimeSeconds: timeInSeconds,
      engagement_level: progression.engagement,
      therapeutic_alliance_score: progression.alliance,
      emotional_state_score: progression.emotional,
      techniques_count: progression.techniques,
      effectiveness_score: progression.effectiveness,
      change_urgency_level: progression.urgency,
      jobId: i + 1, // Sequential job IDs for mock data
    });
  }

  return dataPoints;
};

/**
 * Generate mock chart data for a completed session summary view.
 * Uses a fixed 45-minute session with representative data points.
 */
export const generateSummaryMockChartData = (): ChartDataPoint[] => {
  return generateMockChartData(45, 5);
};

/**
 * Generate mock chart data that simulates a live session in progress.
 * Returns data up to the specified elapsed time.
 *
 * @param elapsedSeconds - How many seconds into the session
 * @returns Array of ChartDataPoint objects up to current time
 */
export const generateLiveMockChartData = (elapsedSeconds: number): ChartDataPoint[] => {
  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  const fullData = generateMockChartData(45, 5);

  // Return only data points up to the current elapsed time
  return fullData.filter(point => point.sessionTimeSeconds <= elapsedSeconds);
};
