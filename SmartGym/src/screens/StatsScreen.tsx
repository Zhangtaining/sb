/**
 * Stats Tab — session summary and per-set exercise history.
 */
import React, {useCallback, useEffect, useState} from 'react';
import {ActivityIndicator, FlatList, StyleSheet, Text, View} from 'react-native';
import {api, ExerciseSetSummary, SessionSummary} from '../api/client';
import {session} from '../store/session';

function FormScoreBadge({score}: {score: number | null}) {
  if (score == null) {
    return <Text style={styles.badgeGray}>—</Text>;
  }
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? '#4CAF50' : pct >= 50 ? '#FF9800' : '#f44336';
  return (
    <View style={[styles.badge, {backgroundColor: color}]}>
      <Text style={styles.badgeText}>{pct}%</Text>
    </View>
  );
}

export function StatsScreen() {
  const trackId = session.get();
  const [history, setHistory] = useState<ExerciseSetSummary[]>([]);
  const [sessionData, setSessionData] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!trackId) {
      return;
    }
    try {
      setLoading(true);
      const hist = await api.getTrackHistory(trackId);
      setHistory(hist.sets);
      // Derive a pseudo-session summary from set history
      if (hist.sets.length > 0) {
        const totalReps = hist.sets.reduce((acc, s) => acc + s.rep_count, 0);
        const scored = hist.sets.filter(s => s.form_score != null);
        const avgForm = scored.length
          ? scored.reduce((a, s) => a + (s.form_score ?? 0), 0) / scored.length
          : null;
        setSessionData({
          id: trackId,
          started_at: hist.sets[0].started_at,
          ended_at: hist.sets[hist.sets.length - 1].ended_at,
          total_reps: totalReps,
          form_score: avgForm,
        });
      }
    } catch {
      // silently ignore
    } finally {
      setLoading(false);
    }
  }, [trackId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#4CAF50" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Session summary card */}
      {sessionData ? (
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Session Summary</Text>
          <View style={styles.summaryRow}>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>{sessionData.total_reps}</Text>
              <Text style={styles.summaryLabel}>Total Reps</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>
                {sessionData.form_score != null
                  ? `${Math.round(sessionData.form_score * 100)}%`
                  : '—'}
              </Text>
              <Text style={styles.summaryLabel}>Avg Form</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryValue}>{history.length}</Text>
              <Text style={styles.summaryLabel}>Sets</Text>
            </View>
          </View>
        </View>
      ) : null}

      {/* Sets list */}
      <FlatList
        data={history}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.list}
        renderItem={({item}) => (
          <View style={styles.setCard}>
            <View style={styles.setHeader}>
              <Text style={styles.setExercise}>{item.exercise_type}</Text>
              <FormScoreBadge score={item.form_score} />
            </View>
            <Text style={styles.setReps}>{item.rep_count} reps</Text>
            <Text style={styles.setTime}>
              {new Date(item.started_at).toLocaleTimeString()}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>No sets recorded yet.</Text>
            <Text style={styles.emptySubText}>Start exercising to see your stats here.</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},
  center: {flex: 1, alignItems: 'center', justifyContent: 'center'},
  summaryCard: {
    backgroundColor: '#1c1c1e',
    margin: 16,
    borderRadius: 16,
    padding: 16,
  },
  summaryTitle: {color: '#aaa', fontSize: 13, letterSpacing: 2, marginBottom: 12},
  summaryRow: {flexDirection: 'row', justifyContent: 'space-around'},
  summaryItem: {alignItems: 'center'},
  summaryValue: {color: '#fff', fontSize: 28, fontWeight: '900'},
  summaryLabel: {color: '#888', fontSize: 12, marginTop: 4},
  list: {paddingHorizontal: 16, paddingBottom: 16},
  setCard: {
    backgroundColor: '#1c1c1e',
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
  },
  setHeader: {flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center'},
  setExercise: {color: '#fff', fontWeight: '700', textTransform: 'capitalize', fontSize: 16},
  setReps: {color: '#4CAF50', fontWeight: '600', marginTop: 4},
  setTime: {color: '#666', fontSize: 12, marginTop: 2},
  badge: {paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6},
  badgeText: {color: '#fff', fontWeight: '700', fontSize: 13},
  badgeGray: {color: '#666', fontWeight: '700'},
  emptyText: {color: '#888', fontSize: 16, marginBottom: 8},
  emptySubText: {color: '#555', fontSize: 13},
});
