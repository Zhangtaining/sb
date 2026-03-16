/**
 * Live Coaching Tab — rep counter, form alerts, guidance log.
 * Phase 2+: set completion card, rest timer, workout checklist, onboarding modal.
 */
import React, {useEffect, useRef, useState} from 'react';
import {FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import Tts from 'react-native-tts';
import {useLiveStream, SetSummary} from '../hooks/useLiveStream';
import {session} from '../store/session';
import {OnboardingScreen} from './OnboardingScreen';

// ── Helpers ────────────────────────────────────────────────────────────────────

function formBadgeColor(score: number): string {
  if (score >= 0.85) {return '#4CAF50';}
  if (score >= 0.65) {return '#FF9800';}
  return '#f44336';
}

function formLabel(score: number): string {
  if (score >= 0.85) {return 'Great';}
  if (score >= 0.65) {return 'OK';}
  return 'Needs Work';
}

function fmtDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
}

function fmtRest(s: number): string {
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

// ── Set Completion Card ────────────────────────────────────────────────────────

function SetCompleteCard({
  summary,
  onDismiss,
}: {
  summary: SetSummary;
  onDismiss: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 8000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <TouchableOpacity style={styles.setCard} onPress={onDismiss} activeOpacity={0.9}>
      <Text style={styles.setCardTitle}>Set Complete</Text>
      <Text style={styles.setCardExercise}>{summary.exerciseType}</Text>
      <View style={styles.setCardRow}>
        <View style={styles.setCardStat}>
          <Text style={styles.setCardStatValue}>{summary.repCount}</Text>
          <Text style={styles.setCardStatLabel}>REPS</Text>
        </View>
        <View
          style={[styles.setCardBadge, {backgroundColor: formBadgeColor(summary.avgFormScore)}]}>
          <Text style={styles.setCardBadgeText}>{formLabel(summary.avgFormScore)}</Text>
        </View>
        {summary.durationMs > 0 ? (
          <View style={styles.setCardStat}>
            <Text style={styles.setCardStatValue}>{fmtDuration(summary.durationMs)}</Text>
            <Text style={styles.setCardStatLabel}>DURATION</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.setCardDismiss}>Tap to dismiss</Text>
    </TouchableOpacity>
  );
}

// ── Main Screen ────────────────────────────────────────────────────────────────

export function LiveCoachingScreen() {
  const trackId = session.get();
  const {
    connected,
    repCount,
    exerciseType,
    lastGuidance,
    lastAlert,
    onboardingGreeting,
    lastSetSummary,
    restS,
  } = useLiveStream(trackId);

  const [showOnboarding, setShowOnboarding] = useState(false);
  const [workoutPlan, setWorkoutPlan] = useState<object | null>(null);
  const [showSetCard, setShowSetCard] = useState(false);
  const [displayedSummary, setDisplayedSummary] = useState<SetSummary | null>(null);

  // Live rest timer (count-up on the client side)
  const [localRestS, setLocalRestS] = useState<number | null>(null);
  const restIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Log of received guidance messages (newest first)
  const guidanceLog = useRef<string[]>([]);
  const [log, setLog] = React.useState<string[]>([]);

  useEffect(() => {
    Tts.setDefaultLanguage('en-US');
  }, []);

  // Show onboarding modal when greeting arrives
  useEffect(() => {
    if (onboardingGreeting) {
      setShowOnboarding(true);
    }
  }, [onboardingGreeting]);

  // Speak new guidance aloud and add to log
  useEffect(() => {
    if (!lastGuidance) {return;}
    Tts.speak(lastGuidance);
    guidanceLog.current = [lastGuidance, ...guidanceLog.current.slice(0, 19)];
    setLog([...guidanceLog.current]);
  }, [lastGuidance]);

  // Show set completion card when a new summary arrives
  useEffect(() => {
    if (!lastSetSummary) {return;}
    setDisplayedSummary(lastSetSummary);
    setShowSetCard(true);
  }, [lastSetSummary]);

  // Start local rest count-up when server restS arrives
  useEffect(() => {
    if (restS !== null) {
      setLocalRestS(restS);
      if (restIntervalRef.current) {clearInterval(restIntervalRef.current);}
      restIntervalRef.current = setInterval(() => {
        setLocalRestS(prev => (prev !== null ? prev + 1 : null));
      }, 1000);
    } else {
      // Rest ended
      if (restIntervalRef.current) {clearInterval(restIntervalRef.current);}
      setLocalRestS(null);
    }
    return () => {
      if (restIntervalRef.current) {clearInterval(restIntervalRef.current);}
    };
  }, [restS]);

  // Clear rest interval when a rep is counted (belt-and-suspenders)
  useEffect(() => {
    if (repCount > 0 && localRestS !== null) {
      if (restIntervalRef.current) {clearInterval(restIntervalRef.current);}
      setLocalRestS(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repCount]);

  return (
    <View style={styles.container}>
      <OnboardingScreen
        visible={showOnboarding}
        greeting={onboardingGreeting ?? ''}
        onDismiss={plan => {
          setShowOnboarding(false);
          if (plan) {setWorkoutPlan(plan);}
        }}
      />

      {/* Connection status */}
      <View style={[styles.statusBar, {backgroundColor: connected ? '#4CAF50' : '#f44336'}]}>
        <Text style={styles.statusText}>{connected ? 'Live' : 'Connecting…'}</Text>
      </View>

      {/* Exercise + rep counter OR rest timer */}
      <View style={styles.statsCard}>
        {localRestS !== null ? (
          <>
            <Text style={styles.restLabel}>REST</Text>
            <Text style={styles.restTimer}>{fmtRest(localRestS)}</Text>
          </>
        ) : (
          <>
            <Text style={styles.exerciseLabel}>{exerciseType ?? '—'}</Text>
            <Text style={styles.repCount}>{repCount}</Text>
            <Text style={styles.repLabel}>REPS</Text>
          </>
        )}
      </View>

      {/* Set completion card */}
      {showSetCard && displayedSummary ? (
        <SetCompleteCard
          summary={displayedSummary}
          onDismiss={() => setShowSetCard(false)}
        />
      ) : null}

      {/* Workout plan checklist */}
      {workoutPlan && !showSetCard ? (
        <WorkoutChecklist plan={workoutPlan} completedSummary={displayedSummary} />
      ) : null}

      {/* Current form alert */}
      {lastAlert ? (
        <View style={styles.alertBanner}>
          <Text style={styles.alertText}>⚠ {lastAlert}</Text>
        </View>
      ) : null}

      {/* Guidance log */}
      <Text style={styles.sectionTitle}>Coaching Log</Text>
      <FlatList
        data={log}
        keyExtractor={(_, i) => String(i)}
        renderItem={({item}) => (
          <View style={styles.logItem}>
            <Text style={styles.logText}>{item}</Text>
          </View>
        )}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No coaching messages yet. Keep exercising!</Text>
        }
        style={styles.logList}
      />
    </View>
  );
}

// ── Workout Plan Checklist ─────────────────────────────────────────────────────

function WorkoutChecklist({
  plan,
  completedSummary,
}: {
  plan: object;
  completedSummary: SetSummary | null;
}) {
  const exercises: Array<{name: string; sets: number; reps: string}> =
    (plan as any).exercises ?? [];
  if (exercises.length === 0) {return null;}

  const completedExercise = completedSummary?.exerciseType ?? null;

  return (
    <View style={styles.checklist}>
      <Text style={styles.checklistTitle}>Today's Plan</Text>
      {exercises.map((ex, i) => {
        const done =
          completedExercise &&
          ex.name.toLowerCase().includes(completedExercise.replace('_', ' '));
        return (
          <View key={i} style={styles.checklistRow}>
            <Text style={[styles.checkmark, done ? styles.checkmarkDone : null]}>
              {done ? '✓' : '○'}
            </Text>
            <Text style={styles.checklistText}>
              {ex.name} — {ex.sets} × {ex.reps}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},
  statusBar: {paddingVertical: 6, alignItems: 'center'},
  statusText: {color: '#fff', fontWeight: '700', fontSize: 13},
  statsCard: {
    alignItems: 'center',
    paddingVertical: 32,
    backgroundColor: '#1c1c1e',
    margin: 16,
    borderRadius: 16,
  },
  exerciseLabel: {color: '#aaa', fontSize: 16, marginBottom: 4, textTransform: 'capitalize'},
  repCount: {color: '#fff', fontSize: 72, fontWeight: '900', lineHeight: 80},
  repLabel: {color: '#888', fontSize: 14, letterSpacing: 4},
  restLabel: {color: '#4CAF50', fontSize: 18, letterSpacing: 3, fontWeight: '700'},
  restTimer: {color: '#fff', fontSize: 64, fontWeight: '900', lineHeight: 72, fontVariant: ['tabular-nums']},
  // Set complete card
  setCard: {
    backgroundColor: '#2a2a2e',
    marginHorizontal: 16,
    marginBottom: 8,
    borderRadius: 14,
    padding: 16,
    borderLeftWidth: 4,
    borderLeftColor: '#4CAF50',
  },
  setCardTitle: {color: '#4CAF50', fontSize: 12, letterSpacing: 2, fontWeight: '700'},
  setCardExercise: {color: '#fff', fontSize: 18, fontWeight: '700', marginTop: 4, textTransform: 'capitalize'},
  setCardRow: {flexDirection: 'row', alignItems: 'center', marginTop: 10, gap: 16},
  setCardStat: {alignItems: 'center'},
  setCardStatValue: {color: '#fff', fontSize: 28, fontWeight: '900'},
  setCardStatLabel: {color: '#888', fontSize: 10, letterSpacing: 2},
  setCardBadge: {borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6},
  setCardBadgeText: {color: '#fff', fontWeight: '700', fontSize: 13},
  setCardDismiss: {color: '#555', fontSize: 11, marginTop: 8},
  // Workout checklist
  checklist: {
    marginHorizontal: 16,
    marginBottom: 8,
    backgroundColor: '#1c1c1e',
    borderRadius: 12,
    padding: 12,
  },
  checklistTitle: {color: '#aaa', fontSize: 11, letterSpacing: 2, marginBottom: 8},
  checklistRow: {flexDirection: 'row', alignItems: 'center', paddingVertical: 4},
  checkmark: {color: '#555', fontSize: 16, marginRight: 8, width: 20},
  checkmarkDone: {color: '#4CAF50'},
  checklistText: {color: '#fff', fontSize: 14},
  // Alerts and log
  alertBanner: {
    backgroundColor: '#b71c1c',
    marginHorizontal: 16,
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  alertText: {color: '#fff', fontSize: 14},
  sectionTitle: {color: '#aaa', fontSize: 13, letterSpacing: 2, marginLeft: 16, marginBottom: 4},
  logList: {flex: 1, marginHorizontal: 16},
  logItem: {
    backgroundColor: '#1c1c1e',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  logText: {color: '#fff', fontSize: 15},
  emptyText: {color: '#555', textAlign: 'center', marginTop: 32},
});
