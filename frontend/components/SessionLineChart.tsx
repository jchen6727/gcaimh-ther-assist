import React from 'react';
import { ComposedChart, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, Area } from 'recharts';
import { Box, Typography } from '@mui/material';
import { ChartDataPoint, formatDataForChart } from '../utils/chartDataUtils';

interface SessionLineChartProps {
  duration: number;
  chartData?: ChartDataPoint[];
}

const SessionLineChart: React.FC<SessionLineChartProps> = ({
  duration,
  chartData = [],
}) => {
  // Only show chart if we have at least 2 real data points
  const data = React.useMemo(() => {
    console.log('SessionLineChart - chartData length:', chartData.length, 'duration:', duration);
    
    if (chartData.length >= 2) {
      // Use only real chart data, no interpolation to avoid extra tick marks
      const formattedData = formatDataForChart(chartData);
      console.log('SessionLineChart - using real data:', formattedData);
      return formattedData;
    } else {
      console.log('SessionLineChart - insufficient data points, showing empty chart');
      return [];
    }
  }, [chartData, duration]);

  // Custom tooltip to show real data values
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <Box sx={{
          backgroundColor: 'white',
          border: '1px solid #e0e0e0',
          borderRadius: 1,
          p: 1.5,
          boxShadow: 2,
        }}>
          <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.5, display: 'block' }}>
            {data.timeDisplay || `${label} min`}
          </Typography>
          {payload.map((item: any, index: number) => (
            <Typography 
              key={index}
              variant="caption" 
              sx={{ 
                color: item.color, 
                display: 'block',
                fontSize: '11px'
              }}
            >
              {item.name}: {item.value}%
            </Typography>
          ))}
          {data.isInterpolated && (
            <Typography variant="caption" sx={{ color: '#666', fontSize: '10px', fontStyle: 'italic' }}>
              Interpolated
            </Typography>
          )}
        </Box>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 16 }}>
        <defs>
          <linearGradient id="colorEngagement" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#0b57d0" stopOpacity={0.8}/>
            <stop offset="95%" stopColor="#0b57d0" stopOpacity={0}/>
          </linearGradient>
          <linearGradient id="colorAlliance" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#9254ea" stopOpacity={0.8}/>
            <stop offset="95%" stopColor="#9254ea" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <XAxis
          type="category"
          dataKey="timeDisplay"
          tick={{ fontSize: 11, fill: '#444746' }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={40}
          tickMargin={6}
          height={28}
        />
        <YAxis
          tick={{ fontSize: 12, fill: '#444746' }}
          axisLine={false}
          tickLine={false}
          domain={[0, 100]}
          ticks={[0, 25, 50, 75, 100]}
          tickMargin={6}
          width={42}
          allowDecimals={false}
          label={{ value: 'Engagement %', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 11, fill: '#666', fontWeight: 500 } }}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* Engagement Level - Blue area */}
        <Area
          type="monotone"
          dataKey="engagement"
          stroke="#0b57d0"
          fillOpacity={1}
          fill="url(#colorEngagement)"
          strokeWidth={2}
          name="Engagement"
        />

        {/* Therapeutic Alliance - Purple area */}
        <Area
          type="monotone"
          dataKey="alliance"
          stroke="#9254ea"
          fillOpacity={0.7}
          fill="url(#colorAlliance)"
          strokeWidth={2}
          name="Alliance"
        />

        {/* Legend - top-right positioning */}
        <Legend
          verticalAlign="top"
          align="right"
          height={20}
          wrapperStyle={{ fontSize: '12px', paddingBottom: 4, paddingRight: 8 }}
          iconSize={10}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
};

export default SessionLineChart;
