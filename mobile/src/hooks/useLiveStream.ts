/**
 * Hook — manages the WebSocket connection to /ws/live/{track_id}.
 * Auto-reconnects after 5s on disconnect.
 */
import {useCallback, useEffect, useRef, useState} from 'react';
import {createLiveSocket, WsMessage} from '../api/client';

const RECONNECT_DELAY_MS = 5000;

interface LiveStreamState {
  connected: boolean;
  repCount: number;
  exerciseType: string | null;
  lastGuidance: string | null;
  lastAlert: string | null;
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
