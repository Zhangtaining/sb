/**
 * Live Coaching Tab — shows live rep count and speaks guidance via TTS.
 */
import React, {useEffect, useRef, useState} from 'react';
import {FlatList, StyleSheet, Text, View} from 'react-native';
import Tts from 'react-native-tts';
import {useLiveStream} from '../hooks/useLiveStream';
import {session} from '../store/session';
import {OnboardingScreen} from './OnboardingScreen';

export function LiveCoachingScreen() {
  const trackId = session.get();
  const {connected, repCount, exerciseType, lastGuidance, lastAlert, onboardingGreeting} =
    useLiveStream(trackId);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [workoutPlan, setWorkoutPlan] = useState<object | null>(null);

  // Show onboarding modal when greeting arrives
  useEffect(() => {
    if (onboardingGreeting) {
      setShowOnboarding(true);
    }
  }, [onboardingGreeting]);

  // Log of received guidance messages (newest first)
  const guidanceLog = useRef<string[]>([]);
  const [log, setLog] = React.useState<string[]>([]);

  useEffect(() => {
    Tts.setDefaultLanguage('en-US');
  }, []);

  // Speak new guidance aloud and add to log
  useEffect(() => {
    if (!lastGuidance) {
      return;
    }
    Tts.speak(lastGuidance);
    guidanceLog.current = [lastGuidance, ...guidanceLog.current.slice(0, 19)];
    setLog([...guidanceLog.current]);
  }, [lastGuidance]);

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

      {/* Exercise + rep counter */}
      <View style={styles.statsCard}>
        <Text style={styles.exerciseLabel}>{exerciseType ?? '—'}</Text>
        <Text style={styles.repCount}>{repCount}</Text>
        <Text style={styles.repLabel}>REPS</Text>
      </View>

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
