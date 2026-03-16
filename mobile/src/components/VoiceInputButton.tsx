/**
 * Mic button that starts/stops speech recording.
 * Glows green while listening. Returns transcript via onTranscript callback.
 */
import React, {useEffect} from 'react';
import {ActivityIndicator, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import {useSpeechToText} from '../hooks/useSpeechToText';

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  size?: number;
}

export function VoiceInputButton({onTranscript, disabled = false, size = 56}: Props) {
  const {isListening, transcript, startListening, stopListening} = useSpeechToText();

  // When we get a final transcript, fire callback and stop
  useEffect(() => {
    if (transcript && !isListening) {
      onTranscript(transcript);
    }
  }, [transcript, isListening, onTranscript]);

  const handlePress = async () => {
    if (isListening) {
      await stopListening();
    } else {
      await startListening();
    }
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity
        onPress={handlePress}
        disabled={disabled}
        style={[
          styles.button,
          {width: size, height: size, borderRadius: size / 2},
          isListening && styles.listening,
          disabled && styles.disabled,
        ]}>
        {isListening ? (
          <ActivityIndicator color="#fff" size="small" />
        ) : (
          <Text style={[styles.icon, {fontSize: size * 0.4}]}>🎤</Text>
        )}
      </TouchableOpacity>
      {isListening && <Text style={styles.hint}>Listening…</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {alignItems: 'center'},
  button: {
    backgroundColor: '#333',
    alignItems: 'center',
    justifyContent: 'center',
  },
  listening: {
    backgroundColor: '#4CAF50',
    shadowColor: '#4CAF50',
    shadowOffset: {width: 0, height: 0},
    shadowOpacity: 0.8,
    shadowRadius: 8,
    elevation: 8,
  },
  disabled: {opacity: 0.4},
  icon: {textAlign: 'center'},
  hint: {color: '#4CAF50', fontSize: 12, marginTop: 4},
});
