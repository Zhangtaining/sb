/**
 * API client — wraps all HTTP and WebSocket calls to the gym API gateway.
 */

const API_BASE_URL = 'http://localhost:8000'; // Override with your server IP in production

// ── Types ────────────────────────────────────────────────────────────────────

export interface SessionSummary {
  id: string;
  started_at: string;
  ended_at: string | null;
  total_reps: number;
  form_score: number | null;
}

export interface ExerciseSetSummary {
  id: string;
  exercise_type: string;
  rep_count: number;
  form_score: number | null;
  started_at: string;
  ended_at: string | null;
  alerts: Record<string, unknown> | null;
}

export interface TrackHistory {
  track_id: string;
  sets: ExerciseSetSummary[];
}

export interface ClipInfo {
  exercise_set_id: string;
  exercise_type: string;
  started_at: string;
  url: string;
}

export interface ReplayData {
  track_id: string;
  clips: ClipInfo[];
}

export type WsEventType = 'rep_counted' | 'form_alert' | 'guidance';

export interface WsMessage {
  type: WsEventType;
  data: Record<string, unknown>;
}

// ── REST helpers ─────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, trackId: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {Authorization: `Bearer ${trackId}`},
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getSession: (sessionId: string, trackId: string) =>
    apiFetch<SessionSummary>(`/sessions/${sessionId}`, trackId),

  getTrackHistory: (trackId: string) =>
    apiFetch<TrackHistory>(`/tracks/${trackId}/history`, trackId),

  getReplay: (trackId: string) =>
    apiFetch<ReplayData>(`/tracks/${trackId}/replay`, trackId),
};

// ── WebSocket ─────────────────────────────────────────────────────────────────

export function createLiveSocket(
  trackId: string,
  onMessage: (msg: WsMessage) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WebSocket {
  const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/live/${trackId}`;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => onOpen?.();
  ws.onclose = () => onClose?.();
  ws.onmessage = event => {
    try {
      const msg = JSON.parse(event.data as string) as WsMessage;
      onMessage(msg);
    } catch {
      // ignore malformed messages
    }
  };

  return ws;
}
