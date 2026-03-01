/**
 * Movement Replay Tab — lists video clips saved by the worker service.
 */
import React, {useCallback, useEffect, useState} from 'react';
import {ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import Video from 'react-native-video';
import {api, ClipInfo} from '../api/client';
import {session} from '../store/session';

export function ReplayScreen() {
  const trackId = session.get();
  const [clips, setClips] = useState<ClipInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!trackId) {
      return;
    }
    try {
      setLoading(true);
      const data = await api.getReplay(trackId);
      setClips(data.clips);
    } catch {
      // silently ignore — empty state shown
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
      <FlatList
        data={clips}
        keyExtractor={item => item.exercise_set_id}
        contentContainerStyle={styles.list}
        renderItem={({item}) => (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.exerciseLabel}>{item.exercise_type}</Text>
              <Text style={styles.timestamp}>
                {new Date(item.started_at).toLocaleTimeString()}
              </Text>
            </View>

            {playingId === item.exercise_set_id ? (
              <Video
                source={{uri: item.url}}
                style={styles.video}
                controls
                resizeMode="contain"
                onEnd={() => setPlayingId(null)}
              />
            ) : (
              <TouchableOpacity
                style={styles.playButton}
                onPress={() => setPlayingId(item.exercise_set_id)}>
                <Text style={styles.playIcon}>▶</Text>
                <Text style={styles.playText}>Play Clip</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.emptyText}>No replay clips yet.</Text>
            <Text style={styles.emptySubText}>Clips are saved when form issues are detected.</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},
  center: {flex: 1, alignItems: 'center', justifyContent: 'center'},
  list: {padding: 16},
  card: {backgroundColor: '#1c1c1e', borderRadius: 12, marginBottom: 16, overflow: 'hidden'},
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 12,
  },
  exerciseLabel: {color: '#fff', fontWeight: '700', textTransform: 'capitalize'},
  timestamp: {color: '#888', fontSize: 13},
  video: {width: '100%', height: 220},
  playButton: {
    alignItems: 'center',
    justifyContent: 'center',
    height: 100,
    flexDirection: 'row',
    gap: 8,
  },
  playIcon: {color: '#4CAF50', fontSize: 24},
  playText: {color: '#4CAF50', fontWeight: '700', fontSize: 16},
  emptyText: {color: '#888', fontSize: 16, marginBottom: 8},
  emptySubText: {color: '#555', fontSize: 13, textAlign: 'center'},
});
