/**
 * HomeScreen — the main tab.
 *
 * Mode 1 (no plan): Full-screen "What do you want to do today?" with
 *   suggestion chips and a mic button.
 *
 * Mode 2 (plan confirmed): Exercise plan as tappable cards.
 *   Tapping a card navigates to Live tab and starts tracking that exercise.
 *   Camera detection triggers a "I can see you" voice cue.
 */
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import Tts from 'react-native-tts';
import {useNavigation} from '@react-navigation/native';
import {api, ChatMessage} from '../api/client';
import {VoiceInputButton} from '../components/VoiceInputButton';
import {useLiveStream} from '../hooks/useLiveStream';
import {session} from '../store/session';

// ── Types ─────────────────────────────────────────────────────────────────────

interface WorkoutExercise {
  name: string;
  sets: number;
  reps: string;
  rest_seconds?: number;
  notes?: string;
  recently_done?: boolean;
}

interface WorkoutPlan {
  focus_area: string;
  duration_minutes: number;
  exercises: WorkoutExercise[];
  note?: string;
}

// Keywords that indicate a trackable exercise
const TRACKED_KEYWORDS = ['squat', 'push up', 'pushup', 'bicep curl', 'lateral raise'];

function isTracked(name: string): boolean {
  const normalized = name.toLowerCase().replace(/_/g, ' ');
  return TRACKED_KEYWORDS.some(keyword => normalized.includes(keyword));
}

// ── Exercise Card ─────────────────────────────────────────────────────────────

function ExerciseCard({
  exercise,
  index,
  completedName,
  isActive,
  onStart,
}: {
  exercise: WorkoutExercise;
  index: number;
  completedName: string | null;
  isActive?: boolean;
  onStart: (exercise: WorkoutExercise) => void;
}) {
  const displayName = exercise.name.replace(/_/g, ' ');
  const isDone =
    completedName !== null &&
    displayName.toLowerCase().includes(completedName.replace('_', ' '));
  const tracked = isTracked(exercise.name);

  return (
    <TouchableOpacity
      style={[styles.card, isDone && styles.cardDone, isActive && !isDone && styles.cardActive]}
      onPress={() => onStart(exercise)}
      activeOpacity={0.8}>
      <View style={styles.cardHeader}>
        <View style={styles.cardLeft}>
          <Text style={styles.cardIndex}>{index + 1}</Text>
          <View>
            <View style={styles.cardNameRow}>
              <Text style={[styles.cardName, isDone && styles.cardNameDone]}>
                {displayName}
              </Text>
              {tracked && (
                <View style={styles.trackedBadge}>
                  <Text style={styles.trackedBadgeText}>📍 tracked</Text>
                </View>
              )}
            </View>
            <Text style={styles.cardSummary}>
              {exercise.sets} sets × {exercise.reps}
              {exercise.rest_seconds ? `  ·  ${exercise.rest_seconds}s rest` : ''}
            </Text>
            {exercise.notes ? (
              <Text style={styles.cardNote}>{exercise.notes}</Text>
            ) : null}
          </View>
        </View>
        <View style={styles.cardRight}>
          {isDone ? (
            <Text style={styles.doneBadge}>✓</Text>
          ) : (
            <>
              {exercise.recently_done && (
                <Text style={styles.warningBadge}>!</Text>
              )}
              <Text style={styles.startHint}>Tap to start →</Text>
            </>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
}

// ── Suggestion chips ──────────────────────────────────────────────────────────

const SUGGESTIONS = [
  {label: 'Build muscle & strength', message: 'I want to build muscle and strength today'},
  {label: 'Cardio & endurance', message: 'I want to do cardio and endurance training'},
  {label: 'Full body workout', message: 'Give me a full body workout'},
  {label: 'Stretch & recover', message: 'I want to stretch and recover today'},
  {label: 'Upper body focus', message: 'I want to focus on upper body today'},
  {label: 'Leg day', message: "It's leg day, give me a legs workout"},
];

function SuggestionChip({label, onPress}: {label: string; onPress: () => void}) {
  return (
    <TouchableOpacity style={styles.chip} onPress={onPress} activeOpacity={0.7}>
      <Text style={styles.chipText}>{label}</Text>
    </TouchableOpacity>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export function HomeScreen() {
  const navigation = useNavigation<any>();
  const trackId = session.get();
  const {lastSetSummary} = useLiveStream(trackId);

  const [plan, setPlan] = useState<WorkoutPlan | null>(null);
  const [activeExerciseIndex, setActiveExerciseIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const history = useRef<ChatMessage[]>([]);

  // Track whether we've already said "I can see you" for this session
  const announcedDetection = useRef(false);
  const cameraCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Greet on mount
  useEffect(() => {
    Tts.speak('What do you want to do today?');
  }, []);

  const speak = useCallback((text: string): Promise<void> => {
    setAiSpeaking(true);
    Tts.speak(text);
    const ms = Math.max(2000, (text.split(' ').length / 130) * 60000);
    return new Promise(resolve =>
      setTimeout(() => {
        setAiSpeaking(false);
        resolve();
      }, ms),
    );
  }, []);

  // Poll camera detection while a plan is active; announce once when seen
  useEffect(() => {
    if (!plan) {
      announcedDetection.current = false;
      if (cameraCheckRef.current) {clearInterval(cameraCheckRef.current);}
      return;
    }

    cameraCheckRef.current = setInterval(async () => {
      if (announcedDetection.current) {return;}
      try {
        const status = await api.getCameraStatus();
        if (status.person_detected) {
          announcedDetection.current = true;
          speak("I can see you! Go ahead whenever you're ready.");
        }
      } catch {}
    }, 2000);

    return () => {
      if (cameraCheckRef.current) {clearInterval(cameraCheckRef.current);}
    };
  }, [plan, speak]);

  // Short plan intro — just announce the focus area
  const startPlanIntro = useCallback(
    async (newPlan: WorkoutPlan) => {
      setActiveExerciseIndex(0);
      const focus = newPlan.focus_area || 'your workout';
      await speak(`OK, let's start ${focus}! Tap any exercise when you're ready to begin.`);
    },
    [speak],
  );

  // Called when user taps an exercise card
  const handleExerciseStart = useCallback(
    async (exercise: WorkoutExercise, index: number) => {
      setActiveExerciseIndex(index);
      session.setExerciseTarget(exercise.reps);
      const name = exercise.name.replace(/_/g, ' ');

      // Set active exercise for the camera pipeline
      console.log('[HomeScreen] trackId:', trackId, 'exercise:', exercise.name);
      if (trackId) {
        try {
          await api.setActiveExercise(trackId, exercise.name);
          console.log('[HomeScreen] setActiveExercise OK');
        } catch (e) {
          console.warn('[HomeScreen] setActiveExercise failed:', e);
        }
      } else {
        console.warn('[HomeScreen] trackId is null — setActiveExercise skipped');
      }

      // Speak a short intro then navigate to Live tab
      speak(`Let's do ${name}. Head to the Live tab — I'll guide you through it.`);
      try {
        const result = await api.exerciseIntro(exercise.name);
        Tts.speak(result.intro);
      } catch {}

      // Navigate to Live coaching
      navigation.navigate('Live');
    },
    [trackId, speak, navigation],
  );

  const handleVoice = useCallback(
    async (text: string) => {
      if (loading) {return;}
      setLoading(true);
      try {
        const result = await api.chat(text, history.current, trackId ?? undefined);
        const response = result.response;

        history.current = [
          ...history.current,
          {role: 'user' as const, content: text},
          {role: 'assistant' as const, content: response},
        ].slice(-20);

        const planMatch =
          response.match(/```json\s*([\s\S]*?)\s*```/) ||
          response.match(/(\{[\s\S]*"exercises"[\s\S]*\})/);
        if (planMatch) {
          try {
            const parsed = JSON.parse(planMatch[1]) as WorkoutPlan;
            if (parsed.exercises?.length) {
              setPlan(parsed);
              startPlanIntro(parsed);
            } else {
              speak(response);
            }
          } catch {
            speak(response);
          }
        } else {
          speak(response);
        }
      } catch {
        speak("Sorry, I couldn't connect. Try again.");
      } finally {
        setLoading(false);
      }
    },
    [loading, speak, trackId, startPlanIntro],
  );

  const completedExercise = lastSetSummary?.exerciseType ?? null;

  // ── Mode 2: Plan confirmed ──────────────────────────────────────────────────
  if (plan) {
    return (
      <View style={styles.container}>
        <View style={styles.planHeader}>
          <Text style={styles.planFocus}>{plan.focus_area}</Text>
          <Text style={styles.planMeta}>
            {plan.duration_minutes} min · {plan.exercises.length} exercises
          </Text>
          {plan.note && <Text style={styles.planNote}>{plan.note}</Text>}
        </View>

        <ScrollView
          style={styles.cardList}
          contentContainerStyle={styles.cardListContent}
          showsVerticalScrollIndicator={false}>
          {plan.exercises.map((ex, i) => (
            <ExerciseCard
              key={i}
              exercise={ex}
              index={i}
              completedName={completedExercise}
              isActive={i === activeExerciseIndex}
              onStart={exercise => handleExerciseStart(exercise, i)}
            />
          ))}
        </ScrollView>

        <View style={styles.bottomBar}>
          {aiSpeaking ? (
            <Text style={styles.speakingHint}>🎙 Coach speaking…</Text>
          ) : (
            <VoiceInputButton onTranscript={handleVoice} size={48} />
          )}
          <TouchableOpacity onPress={() => setPlan(null)} style={styles.resetBtn}>
            <Text style={styles.resetText}>Change plan</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // ── Mode 1: No plan ────────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.noplanContent}
        showsVerticalScrollIndicator={false}>
        <Text style={styles.greeting}>What do you want to do today?</Text>
        <Text style={styles.hint}>Pick a suggestion or talk to your AI coach</Text>

        <View style={styles.suggestions}>
          {SUGGESTIONS.map(s => (
            <SuggestionChip
              key={s.label}
              label={s.label}
              onPress={() => handleVoice(s.message)}
            />
          ))}
        </View>

        {loading ? (
          <ActivityIndicator size="large" color="#4CAF50" style={styles.loader} />
        ) : (
          <TouchableOpacity
            style={styles.startBtn}
            onPress={() =>
              handleVoice('Hello, what workout do you recommend for me today?')
            }
            activeOpacity={0.85}>
            <Text style={styles.startBtnIcon}>🎤</Text>
            <Text style={styles.startBtnText}>Start chatting to your AI coach</Text>
          </TouchableOpacity>
        )}

        {aiSpeaking && (
          <View style={styles.speakingBadge}>
            <Text style={styles.speakingBadgeText}>🎙 Coach speaking…</Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},

  // No-plan mode
  noplanContent: {
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 48,
    paddingBottom: 40,
  },
  greeting: {
    color: '#fff',
    fontSize: 26,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 10,
    lineHeight: 34,
  },
  hint: {
    color: '#666',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 20,
  },
  suggestions: {width: '100%', gap: 12, marginBottom: 32},
  chip: {
    backgroundColor: '#1c1c1e',
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderWidth: 1,
    borderColor: '#2a2a2e',
  },
  chipText: {color: '#fff', fontSize: 16, fontWeight: '500'},
  startBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#4CAF50',
    borderRadius: 16,
    paddingVertical: 18,
    paddingHorizontal: 28,
    width: '100%',
    gap: 10,
    marginBottom: 24,
  },
  startBtnIcon: {fontSize: 20},
  startBtnText: {color: '#fff', fontSize: 17, fontWeight: '700'},
  loader: {marginVertical: 24},
  speakingBadge: {
    backgroundColor: '#1c1c1e',
    borderRadius: 20,
    paddingHorizontal: 18,
    paddingVertical: 8,
  },
  speakingBadgeText: {color: '#4CAF50', fontSize: 14},

  // Plan mode
  planHeader: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 12,
    backgroundColor: '#1c1c1e',
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2e',
  },
  planFocus: {color: '#fff', fontSize: 22, fontWeight: '800'},
  planMeta: {color: '#888', fontSize: 14, marginTop: 2},
  planNote: {color: '#4CAF50', fontSize: 13, marginTop: 6, fontStyle: 'italic'},
  cardList: {flex: 1},
  cardListContent: {padding: 16, paddingBottom: 120},

  // Exercise card
  card: {
    backgroundColor: '#1c1c1e',
    borderRadius: 14,
    marginBottom: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#2a2a2e',
  },
  cardDone: {borderColor: '#4CAF50', opacity: 0.6},
  cardActive: {borderColor: '#4CAF50', borderWidth: 2},
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
  },
  cardLeft: {flexDirection: 'row', alignItems: 'flex-start', gap: 12, flex: 1},
  cardIndex: {
    color: '#555',
    fontSize: 13,
    fontWeight: '700',
    width: 20,
    textAlign: 'center',
    marginTop: 2,
  },
  cardNameRow: {flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap'},
  cardName: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  trackedBadge: {
    backgroundColor: '#1a3320',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#4CAF50',
  },
  trackedBadgeText: {
    color: '#4CAF50',
    fontSize: 11,
    fontWeight: '600',
  },
  cardNameDone: {color: '#4CAF50'},
  cardSummary: {color: '#888', fontSize: 13, marginTop: 2},
  cardNote: {color: '#666', fontSize: 12, marginTop: 4, fontStyle: 'italic'},
  cardRight: {flexDirection: 'row', alignItems: 'center', gap: 8},
  doneBadge: {color: '#4CAF50', fontSize: 20, fontWeight: '700'},
  warningBadge: {
    backgroundColor: '#FF9800',
    color: '#000',
    fontSize: 11,
    fontWeight: '900',
    width: 18,
    height: 18,
    borderRadius: 9,
    textAlign: 'center',
    lineHeight: 18,
  },
  startHint: {color: '#4CAF50', fontSize: 12, fontWeight: '600'},

  // Bottom bar
  bottomBar: {
    backgroundColor: '#1c1c1e',
    borderTopWidth: 1,
    borderTopColor: '#2a2a2e',
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 28,
    alignItems: 'center',
    gap: 8,
  },
  speakingHint: {color: '#4CAF50', fontSize: 14, fontWeight: '600', paddingVertical: 12},
  resetBtn: {paddingVertical: 4},
  resetText: {color: '#444', fontSize: 12},
});
