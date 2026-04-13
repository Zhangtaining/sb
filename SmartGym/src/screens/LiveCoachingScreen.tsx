/**
 * Live Coaching Tab — rep counter, form alerts, guidance log.
 * Phase 2+: set completion card, rest timer, workout checklist, onboarding modal.
 */
import React, {useEffect, useRef, useState} from 'react';
import {FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import Tts from 'react-native-tts';
import {useNavigation} from '@react-navigation/native';
import {useLiveStream, SetSummary} from '../hooks/useLiveStream';
import {api} from '../api/client';
import {session} from '../store/session';
import {OnboardingScreen} from './OnboardingScreen';

function parseTargetReps(reps: string | null): number | null {
  if (!reps) {return null;}
  const parts = reps.split('-');
  const val = parseInt(parts[parts.length - 1], 10);
  return isNaN(val) ? null : val;
}

const REP_WORDS = [
  '', 'One', 'Two', 'Three', 'Four', 'Five',
  'Six', 'Seven', 'Eight', 'Nine', 'Ten',
  'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
  'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen', 'Twenty',
];

function repWord(n: number): string {
  return REP_WORDS[n] ?? String(n);
}

function repCallout(rep: number, target: number | null): string {
  if (target && rep === target) {
    return `${repWord(rep)}! That's your set, well done!`;
  }
  if (target && rep === Math.floor(target / 2)) {
    return `${repWord(rep)}! Halfway there, keep it up!`;
  }
  if (rep % 5 === 0) {
    return `${repWord(rep)}! Great work!`;
  }
  return repWord(rep);
}

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
  onNext,
}: {
  summary: SetSummary;
  onNext: () => void;
}) {
  return (
    <View style={styles.setCard}>
      <Text style={styles.setCardTitle}>✓ Set Complete</Text>
      <Text style={styles.setCardExercise}>{summary.exerciseType.replace(/_/g, ' ')}</Text>
      <View style={styles.setCardRow}>
        <View style={styles.setCardStat}>
          <Text style={styles.setCardStatValue}>{summary.repCount}</Text>
          <Text style={styles.setCardStatLabel}>REPS</Text>
        </View>
        <View style={[styles.setCardBadge, {backgroundColor: formBadgeColor(summary.avgFormScore)}]}>
          <Text style={styles.setCardBadgeText}>{formLabel(summary.avgFormScore)}</Text>
        </View>
        {summary.durationMs > 0 && (
          <View style={styles.setCardStat}>
            <Text style={styles.setCardStatValue}>{fmtDuration(summary.durationMs)}</Text>
            <Text style={styles.setCardStatLabel}>DURATION</Text>
          </View>
        )}
      </View>
      <TouchableOpacity style={styles.nextBtn} onPress={onNext} activeOpacity={0.8}>
        <Text style={styles.nextBtnText}>Next Exercise →</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Main Screen ────────────────────────────────────────────────────────────────

export function LiveCoachingScreen() {
  const trackId = session.get();
  const navigation = useNavigation<any>();
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
  const [completedSummary, setCompletedSummary] = useState<SetSummary | null>(null);
  const [frozenRepCount, setFrozenRepCount] = useState<number | null>(null);

  // Live rest timer (count-up on the client side)
  const [localRestS, setLocalRestS] = useState<number | null>(null);
  const restIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Unified coaching log — guidance + form alerts (newest first)
  interface LogEntry { text: string; type: 'guidance' | 'alert'; }
  const coachingLog = useRef<LogEntry[]>([]);
  const [log, setLog] = React.useState<LogEntry[]>([]);

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
    coachingLog.current = [{text: lastGuidance, type: 'guidance'}, ...coachingLog.current.slice(0, 29)];
    setLog([...coachingLog.current]);
  }, [lastGuidance]);

  // Speak rep number aloud on every new rep
  useEffect(() => {
    if (repCount <= 0) {return;}
    const target = parseTargetReps(session.getExerciseTarget());
    Tts.speak(repCallout(repCount, target));
  }, [repCount]);

  // Speak form alerts and add to log
  useEffect(() => {
    if (!lastAlert) {return;}
    Tts.speak(lastAlert);
    coachingLog.current = [{text: lastAlert, type: 'alert'}, ...coachingLog.current.slice(0, 29)];
    setLog([...coachingLog.current]);
  }, [lastAlert]);

  // Freeze count and show completion card when set ends
  useEffect(() => {
    if (!lastSetSummary) {return;}
    setFrozenRepCount(lastSetSummary.repCount);
    setCompletedSummary(lastSetSummary);
    Tts.speak(`Set complete! ${lastSetSummary.repCount} reps. Great work! Rest up, then tap Next Exercise when you're ready.`);
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

      {/* Tracking state banner */}
      {connected && (
        <View style={[styles.trackingBanner, exerciseType ? styles.trackingBannerActive : styles.trackingBannerWaiting]}>
          <Text style={styles.trackingDot}>{exerciseType ? '●' : '○'}</Text>
          <Text style={styles.trackingText}>
            {exerciseType
              ? `Tracking: ${exerciseType.replace(/_/g, ' ')}`
              : 'Waiting for movement…'}
          </Text>
        </View>
      )}

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
            <View style={styles.repRow}>
              <Text style={[styles.repCount, completedSummary ? styles.repCountDone : null]}>
                {frozenRepCount ?? repCount}
              </Text>
              {parseTargetReps(session.getExerciseTarget()) !== null && (
                <Text style={styles.repTarget}>/{parseTargetReps(session.getExerciseTarget())}</Text>
              )}
            </View>
            <Text style={styles.repLabel}>{completedSummary ? 'SET DONE' : 'REPS'}</Text>
          </>
        )}
      </View>

      {/* Set completion card */}
      {completedSummary ? (
        <SetCompleteCard
          summary={completedSummary}
          onNext={() => {
            const tid = session.get();
            if (tid) {api.clearActiveExercise(tid).catch(() => {});}
            setCompletedSummary(null);
            setFrozenRepCount(null);
            navigation.navigate('Today');
          }}
        />
      ) : null}

      {/* Workout plan checklist */}
      {workoutPlan && !completedSummary ? (
        <WorkoutChecklist plan={workoutPlan} completedSummary={null} />
      ) : null}

      {/* Unified coaching log */}
      <Text style={styles.sectionTitle}>Coaching Log</Text>
      <FlatList
        data={log}
        keyExtractor={(_, i) => String(i)}
        renderItem={({item}) => (
          <View style={item.type === 'alert' ? styles.logItemAlert : styles.logItem}>
            {item.type === 'alert' && (
              <Text style={styles.logAlertLabel}>⚠ Form</Text>
            )}
            <Text style={item.type === 'alert' ? styles.logTextAlert : styles.logText}>
              {item.text}
            </Text>
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
  trackingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
  },
  trackingBannerActive: {backgroundColor: '#0d2b0d'},
  trackingBannerWaiting: {backgroundColor: '#1c1c1e'},
  trackingDot: {fontSize: 10, color: '#4CAF50'},
  trackingText: {fontSize: 13, fontWeight: '600', color: '#4CAF50', textTransform: 'capitalize'},
  statsCard: {
    alignItems: 'center',
    paddingVertical: 32,
    backgroundColor: '#1c1c1e',
    margin: 16,
    borderRadius: 16,
  },
  exerciseLabel: {color: '#aaa', fontSize: 16, marginBottom: 4, textTransform: 'capitalize'},
  repRow: {flexDirection: 'row', alignItems: 'flex-end'},
  repCount: {color: '#fff', fontSize: 72, fontWeight: '900', lineHeight: 80},
  repCountDone: {color: '#4CAF50'},
  repTarget: {color: '#555', fontSize: 36, fontWeight: '700', lineHeight: 80, marginBottom: 4},
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
  nextBtn: {
    marginTop: 14,
    backgroundColor: '#4CAF50',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  nextBtnText: {color: '#fff', fontWeight: '700', fontSize: 15},
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
  sectionTitle: {color: '#aaa', fontSize: 13, letterSpacing: 2, marginLeft: 16, marginBottom: 4},
  logList: {flex: 1, marginHorizontal: 16},
  logItem: {
    backgroundColor: '#1c1c1e',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  logItemAlert: {
    backgroundColor: '#1c1c1e',
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
    borderLeftWidth: 3,
    borderLeftColor: '#FF9800',
  },
  logAlertLabel: {color: '#FF9800', fontSize: 10, fontWeight: '700', letterSpacing: 1, marginBottom: 3},
  logText: {color: '#fff', fontSize: 15, lineHeight: 21},
  logTextAlert: {color: '#ddd', fontSize: 14, lineHeight: 20},
  emptyText: {color: '#555', textAlign: 'center', marginTop: 32},
});
