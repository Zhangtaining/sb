/**
 * API client — wraps all HTTP and WebSocket calls to the gym API gateway.
 */

const API_BASE_URL = 'http://192.168.1.151:8000'; // Mac's LAN IP — phone must be on same WiFi

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

// ── Phase 2 types ─────────────────────────────────────────────────────────────

export interface ConversationResponse {
  id: string;
  person_id: string;
  session_id: string | null;
  started_at: string;
}

export interface ChatResponse {
  conversation_id: string;
  user_message: string;
  assistant_response: string;
}

export interface MessageResponse {
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface PersonProfile {
  name: string;
  goals: string[];
  injury_notes: string;
  member_since: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface StatelessChatReply {
  response: string;
}

export type WsEventType = 'rep_counted' | 'form_alert' | 'guidance' | 'onboarding' | 'onboarding_plan';

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

async function apiPost<T>(path: string, body: unknown, trackId?: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(trackId ? {Authorization: `Bearer ${trackId}`} : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API POST ${path} failed: ${res.status}`);
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

  // ── Phase 2: Conversations ───────────────────────────────────────────────

  createConversation: (personId: string, sessionId?: string) =>
    apiPost<ConversationResponse>('/conversations', {
      person_id: personId,
      session_id: sessionId ?? null,
    }),

  sendMessage: (conversationId: string, text: string) =>
    apiPost<ChatResponse>(`/conversations/${conversationId}/messages`, {text}),

  getMessages: (conversationId: string) =>
    apiFetch<MessageResponse[]>(`/conversations/${conversationId}/messages`, ''),

  // ── Phase 1: Stateless anonymous chat ────────────────────────────────────
  chat: (message: string, history: ChatMessage[], trackId?: string) =>
    apiPost<StatelessChatReply>('/chat', {message, history, track_id: trackId ?? null}),

  exerciseIntro: (exerciseName: string) =>
    apiPost<{intro: string}>('/chat/exercise-intro', {exercise_name: exerciseName}),

  setActiveExercise: (trackId: string, exerciseName: string, cameraId = 'cam-01') =>
    apiPost<{active_exercise: string}>(`/tracks/${trackId}/active-exercise`, {
      exercise_name: exerciseName,
      camera_id: cameraId,
    }),

  clearActiveExercise: (trackId: string, cameraId = 'cam-01') =>
    fetch(`${API_BASE_URL}/tracks/${trackId}/active-exercise?camera_id=${cameraId}`, {
      method: 'DELETE',
    }),

  getCameraStatus: (cameraId = 'cam-01') =>
    fetch(`${API_BASE_URL}/cameras/${cameraId}/status`)
      .then(r => r.json() as Promise<{camera_id: string; camera_online: boolean; person_detected: boolean}>),
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
