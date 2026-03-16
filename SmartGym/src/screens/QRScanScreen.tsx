/**
 * QR Scan Screen — scans a QR code or manually enters a track_id.
 * Manual entry fallback is used in the simulator (no camera).
 */
import React, {useCallback, useState} from 'react';
import {
  Alert,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import {session} from '../store/session';

interface Props {
  onSessionStarted: () => void;
}

export function QRScanScreen({onSessionStarted}: Props) {
  const [manualId, setManualId] = useState('');

  const handleManualEntry = useCallback(async () => {
    const value = manualId.trim();
    if (!value) {
      Alert.alert('Error', 'Please enter a track ID.');
      return;
    }
    await session.save(value);
    onSessionStarted();
  }, [manualId, onSessionStarted]);

  return (
    <View style={styles.center}>
      <Text style={styles.title}>Smart Gym</Text>
      <Text style={styles.subtitle}>Enter your session track ID</Text>

      <TextInput
        style={styles.input}
        placeholder="e.g. test-track-1"
        placeholderTextColor="#555"
        value={manualId}
        onChangeText={setManualId}
        autoCapitalize="none"
        autoCorrect={false}
      />

      <TouchableOpacity style={styles.button} onPress={handleManualEntry}>
        <Text style={styles.buttonText}>Start Session</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#111',
    padding: 32,
  },
  title: {
    color: '#fff',
    fontSize: 32,
    fontWeight: '900',
    marginBottom: 8,
  },
  subtitle: {
    color: '#888',
    fontSize: 16,
    marginBottom: 32,
  },
  input: {
    width: '100%',
    backgroundColor: '#1c1c1e',
    color: '#fff',
    borderRadius: 10,
    padding: 16,
    fontSize: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#333',
  },
  button: {
    width: '100%',
    backgroundColor: '#4CAF50',
    paddingVertical: 16,
    borderRadius: 10,
    alignItems: 'center',
  },
  buttonText: {color: '#fff', fontWeight: '700', fontSize: 16},
});
