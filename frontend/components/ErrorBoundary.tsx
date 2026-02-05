import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Typography, Button } from '@mui/material';
import { RefreshOutlined, ErrorOutline } from '@mui/icons-material';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Caught error:', error.message);
    console.error('[ErrorBoundary] Component stack:', errorInfo.componentStack);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            backgroundColor: '#f8f9fa',
            padding: 4,
            textAlign: 'center',
          }}
        >
          <ErrorOutline sx={{ fontSize: 64, color: '#ef4444', mb: 2 }} />
          <Typography variant="h5" sx={{ fontWeight: 600, mb: 1, color: '#1a1a2e' }}>
            Session Encountered an Error
          </Typography>
          <Typography variant="body1" sx={{ color: '#666', mb: 3, maxWidth: 480 }}>
            An unexpected error occurred. Your session data is preserved.
            Click below to resume.
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: '#999',
              mb: 3,
              fontFamily: 'monospace',
              backgroundColor: '#f0f0f0',
              px: 2,
              py: 1,
              borderRadius: 1,
              maxWidth: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {this.state.error?.message || 'Unknown error'}
          </Typography>
          <Button
            variant="contained"
            startIcon={<RefreshOutlined />}
            onClick={this.handleReset}
            sx={{
              backgroundColor: '#1a73e8',
              textTransform: 'none',
              fontWeight: 600,
              px: 4,
              py: 1.5,
              borderRadius: 2,
              '&:hover': { backgroundColor: '#1557b0' },
            }}
          >
            Resume Session
          </Button>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
