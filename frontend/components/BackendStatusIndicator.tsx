import React, { useState, useEffect } from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import { Cloud, CloudOff, CloudQueue } from '@mui/icons-material';
import axios from 'axios';

type ConnectionStatus = 'checking' | 'connected' | 'mock' | 'error';

const BackendStatusIndicator: React.FC = () => {
  const [status, setStatus] = useState<ConnectionStatus>('checking');
  const [backendUrl, setBackendUrl] = useState<string>('');

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_ANALYSIS_API;

    if (!apiUrl || apiUrl === '' || apiUrl === 'undefined') {
      setStatus('mock');
      setBackendUrl('No backend configured');
      return;
    }

    setBackendUrl(apiUrl);

    // Ping the backend with an invalid action to check connectivity
    // The backend will return 400 with a known error message if it's reachable
    const checkConnection = async () => {
      try {
        const response = await axios.post(
          `${apiUrl}/therapy_analysis`,
          { action: 'health_check' },
          { timeout: 5000, headers: { 'Content-Type': 'application/json' } }
        );
        // If we get any response, the backend is reachable
        setStatus('connected');
      } catch (err: any) {
        if (err.response) {
          // Got a response (even 400/405) — backend is reachable
          setStatus('connected');
        } else {
          // Network error — backend is not reachable
          setStatus('error');
        }
      }
    };

    checkConnection();
  }, []);

  const config: Record<ConnectionStatus, {
    color: string;
    bgColor: string;
    icon: React.ReactNode;
    label: string;
    tooltip: string;
  }> = {
    checking: {
      color: '#f59e0b',
      bgColor: 'rgba(245, 158, 11, 0.08)',
      icon: <CloudQueue sx={{ fontSize: 16, color: '#f59e0b' }} />,
      label: 'Checking...',
      tooltip: 'Checking backend connection',
    },
    connected: {
      color: '#10b981',
      bgColor: 'rgba(16, 185, 129, 0.08)',
      icon: <Cloud sx={{ fontSize: 16, color: '#10b981' }} />,
      label: 'GCP Connected',
      tooltip: `Backend connected: ${backendUrl}`,
    },
    mock: {
      color: '#f59e0b',
      bgColor: 'rgba(245, 158, 11, 0.08)',
      icon: <CloudOff sx={{ fontSize: 16, color: '#f59e0b' }} />,
      label: 'Mock Mode',
      tooltip: 'No backend configured — using mock data',
    },
    error: {
      color: '#ef4444',
      bgColor: 'rgba(239, 68, 68, 0.08)',
      icon: <CloudOff sx={{ fontSize: 16, color: '#ef4444' }} />,
      label: 'Disconnected',
      tooltip: `Cannot reach backend at ${backendUrl}`,
    },
  };

  const current = config[status];

  return (
    <Tooltip title={current.tooltip} arrow placement="bottom">
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.75,
          px: 1.5,
          py: 0.5,
          borderRadius: '16px',
          backgroundColor: current.bgColor,
          border: `1px solid ${current.color}20`,
          cursor: 'default',
          transition: 'all 0.3s ease',
        }}
      >
        {current.icon}
        <Typography
          sx={{
            fontSize: '12px',
            fontWeight: 600,
            color: current.color,
            letterSpacing: '0.02em',
          }}
        >
          {current.label}
        </Typography>
        <Box
          sx={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: current.color,
            animation: status === 'checking' ? 'pulse 1.5s infinite' :
                       status === 'connected' ? 'none' : 'none',
            '@keyframes pulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.3 },
            },
          }}
        />
      </Box>
    </Tooltip>
  );
};

export default BackendStatusIndicator;
