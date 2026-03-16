/**
 * Hook — manages the WebSocket connection to /ws/live/{track_id}.
 * Auto-reconnects after 5s on disconnect.
 */
import {useCallback, useEffect, useRef, useState} from 'react';
import {createLiveSocket, WsMessage} from '../api/client';

const RECONNECT_DELAY_MS = 5000;

export interface SetSummary {
  exerciseType: string;
  repCount: number;
  avgFormScore: number;
  durationMs: number;
}

interface LiveStreamState {
  connected: boolean;
  repCount: number;
  exerciseType: string | null;
  lastGuidance: string | null;
  lastAlert: string | null;
  onboardingGreeting: string | null;
  lastSetSummary: SetSummary | null;
  restS: number | null; // seconds currently resting, null = not resting
}

export function useLiveStream(trackId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [state, setState] = useState<LiveStreamState>({
    connected: false,
    repCount: 0,
    exerciseType: null,
    lastGuidance: null,
    lastAlert: null,
    onboardingGreeting: null,
    lastSetSummary: null,
    restS: null,
  });

  const connect = useCallback(() => {
    if (!trackId) {
      return;
    }
    wsRef.current = createLiveSocket(
      trackId,
      (msg: WsMessage) => {
        if (msg.type === 'rep_counted') {
          setState(s => ({
            ...s,
            repCount: (msg.data.rep_count as number) ?? s.repCount,
            exerciseType: (msg.data.exercise_type as string) ?? s.exerciseType,
            // Clear rest timer when reps start
            restS: null,
          }));
        } else if (msg.type === 'form_alert') {
          setState(s => ({
            ...s,
            lastAlert: msg.data.alert_message as string,
          }));
        } else if (msg.type === 'guidance') {
          setState(s => ({
            ...s,
            lastGuidance: msg.data.message as string,
          }));
        } else if (msg.type === 'onboarding' || msg.type === 'onboarding_plan') {
          setState(s => ({
            ...s,
            onboardingGreeting: msg.data.message as string,
          }));
        } else if (msg.type === 'set_complete') {
          setState(s => ({
            ...s,
            lastSetSummary: {
              exerciseType: msg.data.exercise_type as string,
              repCount: msg.data.rep_count as number,
              avgFormScore: msg.data.avg_form_score as number,
              durationMs: msg.data.duration_ms as number,
            },
            repCount: 0, // reset for next set
          }));
        } else if (msg.type === 'rest_update') {
          const finished = msg.data.finished as boolean;
          setState(s => ({
            ...s,
            restS: finished ? null : (msg.data.rest_s as number),
          }));
        }
      },
      () => setState(s => ({...s, connected: true})),
      () => {
        setState(s => ({...s, connected: false}));
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      },
    );
  }, [trackId]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return state;
}
