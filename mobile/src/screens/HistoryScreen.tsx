/**
 * History tab — calendar heatmap of workout days + personal bests.
 * Uses react-native-calendars for the calendar view.
 */
import React, {useEffect, useState} from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import {Calendar} from 'react-native-calendars';
import {api, ExerciseSetSummary, TrackHistory} from '../api/client';
import {session} from '../store/session';

interface DayData {
  date: string;
  sets: ExerciseSetSummary[];
  totalReps: number;
}

interface PersonalBest {
  exercise: string;
  reps: number;
  date: string;
}

function repColor(totalReps: number): string {
  if (totalReps >= 60) {return '#1b5e20';}
  if (totalReps >= 30) {return '#2e7d32';}
  if (totalReps >= 10) {return '#388e3c';}
  return '#66bb6a';
}

export function HistoryScreen() {
  const [history, setHistory] = useState<TrackHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [markedDates, setMarkedDates] = useState<Record<string, unknown>>({});
  const [dayMap, setDayMap] = useState<Record<string, DayData>>({});
  const [personalBests, setPersonalBests] = useState<PersonalBest[]>([]);

  const trackId = session.get();

  useEffect(() => {
    if (!trackId) {
      setLoading(false);
      return;
    }

    api
      .getTrackHistory(trackId)
      .then(data => {
        setHistory(data);
        processHistory(data);
      })
      .catch(() => setLoading(false))
      .finally(() => setLoading(false));
  }, [trackId]);

  const processHistory = (data: TrackHistory) => {
    // Group sets by date
    const map: Record<string, DayData> = {};
    for (const s of data.sets) {
      const date = s.started_at.slice(0, 10);
      if (!map[date]) {
        map[date] = {date, sets: [], totalReps: 0};
      }
      map[date].sets.push(s);
      map[date].totalReps += s.rep_count;
    }
    setDayMap(map);

    // Build marked dates for calendar
    const marked: Record<string, unknown> = {};
    for (const [date, day] of Object.entries(map)) {
      marked[date] = {
        selected: true,
        selectedColor: repColor(day.totalReps),
        marked: true,
        dotColor: '#fff',
      };
    }
    setMarkedDates(marked);

    // Compute personal bests per exercise
    const bestMap: Record<string, {reps: number; date: string}> = {};
    for (const s of data.sets) {
      const existing = bestMap[s.exercise_type];
      if (!existing || s.rep_count > existing.reps) {
        bestMap[s.exercise_type] = {reps: s.rep_count, date: s.started_at.slice(0, 10)};
      }
    }
    setPersonalBests(
      Object.entries(bestMap)
        .map(([exercise, {reps, date}]) => ({exercise, reps, date}))
        .sort((a, b) => b.reps - a.reps),
    );
  };

  const handleDayPress = (day: {dateString: string}) => {
    setSelectedDate(prev => (prev === day.dateString ? null : day.dateString));
  };

  const selectedDay = selectedDate ? dayMap[selectedDate] : null;

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#4CAF50" size="large" />
      </View>
    );
  }

  if (!trackId) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyText}>No session active. Scan a QR code to start.</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Calendar */}
      <Calendar
        markedDates={{
          ...markedDates,
          ...(selectedDate
            ? {
                [selectedDate]: {
                  ...(markedDates[selectedDate] as object ?? {}),
                  selected: true,
                  selectedColor: '#4CAF50',
                },
              }
            : {}),
        }}
        onDayPress={handleDayPress}
        theme={{
          backgroundColor: '#1c1c1e',
          calendarBackground: '#1c1c1e',
          textSectionTitleColor: '#aaa',
          selectedDayBackgroundColor: '#4CAF50',
          selectedDayTextColor: '#fff',
          todayTextColor: '#4CAF50',
          dayTextColor: '#fff',
          textDisabledColor: '#444',
          dotColor: '#4CAF50',
          monthTextColor: '#fff',
          arrowColor: '#4CAF50',
        }}
        style={styles.calendar}
      />

      {/* Selected day details */}
      {selectedDay && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>
            {selectedDate} — {selectedDay.totalReps} total reps
          </Text>
          {selectedDay.sets.map((s, i) => (
            <View key={i} style={styles.setRow}>
              <Text style={styles.exerciseName}>{s.exercise_type.replace(/_/g, ' ')}</Text>
              <View style={styles.setMeta}>
                <Text style={styles.repsText}>{s.rep_count} reps</Text>
                {s.form_score != null && (
                  <View
                    style={[
                      styles.formBadge,
                      {
                        backgroundColor:
                          s.form_score >= 0.8
                            ? '#2e7d32'
                            : s.form_score >= 0.5
                            ? '#f57c00'
                            : '#c62828',
                      },
                    ]}>
                    <Text style={styles.formBadgeText}>
                      {Math.round(s.form_score * 100)}%
                    </Text>
                  </View>
                )}
              </View>
            </View>
          ))}
        </View>
      )}

      {/* Personal bests */}
      {personalBests.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Personal Bests 🏆</Text>
          {personalBests.slice(0, 8).map((pb, i) => (
            <View key={i} style={styles.pbRow}>
              <Text style={styles.pbExercise}>{pb.exercise.replace(/_/g, ' ')}</Text>
              <View style={styles.pbRight}>
                <Text style={styles.pbReps}>{pb.reps} reps</Text>
                <Text style={styles.pbDate}>{pb.date}</Text>
              </View>
            </View>
          ))}
        </View>
      )}

      {/* Empty state */}
      {(!history || history.sets.length === 0) && (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyText}>No workout history yet.</Text>
          <Text style={styles.emptyHint}>Complete a session to see your progress here.</Text>
        </View>
      )}

      {/* Legend */}
      <View style={styles.legend}>
        <Text style={styles.legendTitle}>Activity Level</Text>
        <View style={styles.legendRow}>
          {[10, 30, 60, 90].map((reps, i) => (
            <View key={i} style={styles.legendItem}>
              <View style={[styles.legendDot, {backgroundColor: repColor(reps)}]} />
              <Text style={styles.legendLabel}>{reps}+ reps</Text>
            </View>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},
  content: {paddingBottom: 40},
  center: {flex: 1, backgroundColor: '#111', alignItems: 'center', justifyContent: 'center', padding: 24},
  calendar: {borderRadius: 12, marginHorizontal: 16, marginTop: 12, overflow: 'hidden'},
  section: {margin: 16, backgroundColor: '#1c1c1e', borderRadius: 12, padding: 14},
  sectionTitle: {color: '#aaa', fontSize: 12, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10},
  setRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  exerciseName: {color: '#fff', fontSize: 15, textTransform: 'capitalize', flex: 1},
  setMeta: {flexDirection: 'row', alignItems: 'center', gap: 8},
  repsText: {color: '#aaa', fontSize: 14},
  formBadge: {borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3},
  formBadgeText: {color: '#fff', fontSize: 12, fontWeight: '700'},
  pbRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#2a2a2a',
  },
  pbExercise: {color: '#fff', fontSize: 15, textTransform: 'capitalize', flex: 1},
  pbRight: {alignItems: 'flex-end'},
  pbReps: {color: '#FFD700', fontSize: 15, fontWeight: '700'},
  pbDate: {color: '#555', fontSize: 12},
  emptyContainer: {alignItems: 'center', padding: 40},
  emptyText: {color: '#aaa', fontSize: 16, fontWeight: '600'},
  emptyHint: {color: '#555', fontSize: 14, marginTop: 8},
  legend: {margin: 16},
  legendTitle: {color: '#555', fontSize: 12, marginBottom: 6},
  legendRow: {flexDirection: 'row', gap: 16},
  legendItem: {flexDirection: 'row', alignItems: 'center', gap: 4},
  legendDot: {width: 12, height: 12, borderRadius: 2},
  legendLabel: {color: '#555', fontSize: 12},
});
