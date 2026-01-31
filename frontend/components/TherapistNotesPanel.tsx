import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Chip,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  ExpandLess,
  ExpandMore,
  Delete,
  Note,
} from '@mui/icons-material';

interface TherapistNotesPanelProps {
  sessionInstanceId: string;
}

type SaveStatus = 'not_saved' | 'saving' | 'saved';

const TherapistNotesPanel: React.FC<TherapistNotesPanelProps> = ({ sessionInstanceId }) => {
  const [notes, setNotes] = useState('');
  const [expanded, setExpanded] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('not_saved');
  const [isDirty, setIsDirty] = useState(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const hasLoadedRef = useRef(false);

  const storageKey = `therapist-notes-${sessionInstanceId}`;

  // Load notes from localStorage on mount
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    try {
      const savedNotes = localStorage.getItem(storageKey);
      if (savedNotes) {
        setNotes(savedNotes);
        setSaveStatus('saved');
      }
    } catch (error) {
      console.error('[TherapistNotes] Failed to load notes from localStorage:', error);
    }
  }, [storageKey]);

  // Save notes to localStorage
  const saveNotes = useCallback((text: string) => {
    try {
      localStorage.setItem(storageKey, text);
      setSaveStatus('saved');
      setIsDirty(false);
    } catch (error) {
      console.error('[TherapistNotes] Failed to save notes to localStorage:', error);
    }
  }, [storageKey]);

  // Debounced autosave
  const debouncedSave = useCallback((text: string) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    setSaveStatus('saving');
    setIsDirty(true);

    debounceTimerRef.current = setTimeout(() => {
      saveNotes(text);
    }, 500);
  }, [saveNotes]);

  // Handle text change
  const handleNotesChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = event.target.value;
    setNotes(newText);
    debouncedSave(newText);
  };

  // Handle clear
  const handleClear = () => {
    setNotes('');
    saveNotes('');
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const getStatusChip = () => {
    switch (saveStatus) {
      case 'saving':
        return (
          <Chip
            label="Saving..."
            size="small"
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: '#fef3c7',
              color: '#d97706',
              fontWeight: 500,
            }}
          />
        );
      case 'saved':
        return (
          <Chip
            label="Saved"
            size="small"
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: '#d1fae5',
              color: '#059669',
              fontWeight: 500,
            }}
          />
        );
      case 'not_saved':
      default:
        return (
          <Chip
            label="Not saved yet"
            size="small"
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: '#f3f4f6',
              color: '#6b7280',
              fontWeight: 500,
            }}
          />
        );
    }
  };

  return (
    <Paper
      elevation={2}
      sx={{
        position: 'sticky',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        borderRadius: '8px 8px 0 0',
        overflow: 'hidden',
        bgcolor: 'white',
        borderTop: '1px solid #e5e7eb',
      }}
    >
      {/* Header */}
      <Box
        onClick={() => setExpanded(!expanded)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 2,
          py: 1,
          cursor: 'pointer',
          bgcolor: '#f9fafb',
          borderBottom: expanded ? '1px solid #e5e7eb' : 'none',
          '&:hover': {
            bgcolor: '#f3f4f6',
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Note sx={{ fontSize: 20, color: '#6b7280' }} />
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 600,
              fontSize: '0.875rem',
              color: '#374151',
            }}
          >
            Clinician Notes
          </Typography>
          {getStatusChip()}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {expanded && notes.length > 0 && (
            <Button
              size="small"
              startIcon={<Delete sx={{ fontSize: 16 }} />}
              onClick={(e) => {
                e.stopPropagation();
                handleClear();
              }}
              sx={{
                color: '#6b7280',
                fontSize: '0.75rem',
                textTransform: 'none',
                minWidth: 'auto',
                px: 1,
                '&:hover': {
                  bgcolor: 'rgba(107, 114, 128, 0.08)',
                  color: '#ef4444',
                },
              }}
            >
              Clear
            </Button>
          )}
          <IconButton
            size="small"
            sx={{ color: '#6b7280' }}
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
          >
            {expanded ? <ExpandMore /> : <ExpandLess />}
          </IconButton>
        </Box>
      </Box>

      {/* Notes content */}
      <Collapse in={expanded}>
        <Box sx={{ p: 2 }}>
          <TextField
            multiline
            rows={3}
            fullWidth
            placeholder="Type your private session notes here... (saved locally only)"
            value={notes}
            onChange={handleNotesChange}
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                fontSize: '0.875rem',
                bgcolor: '#fafafa',
                '& fieldset': {
                  borderColor: '#e5e7eb',
                },
                '&:hover fieldset': {
                  borderColor: '#d1d5db',
                },
                '&.Mui-focused fieldset': {
                  borderColor: '#0b57d0',
                },
              },
              '& .MuiInputBase-input::placeholder': {
                color: '#9ca3af',
                opacity: 1,
              },
            }}
          />
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mt: 1,
              color: '#9ca3af',
              fontSize: '0.7rem',
            }}
          >
            Notes are saved locally in your browser and are not shared or synced.
          </Typography>
        </Box>
      </Collapse>
    </Paper>
  );
};

export default TherapistNotesPanel;
