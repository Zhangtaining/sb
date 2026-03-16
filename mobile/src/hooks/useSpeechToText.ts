/**
 * Speech-to-text hook using @react-native-voice/voice.
 *
 * Usage:
 *   const {isListening, transcript, startListening, stopListening, error} = useSpeechToText();
 */
import {useCallback, useEffect, useRef, useState} from 'react';
import Voice, {
  SpeechResultsEvent,
  SpeechErrorEvent,
} from '@react-native-voice/voice';

export interface UseSpeechToTextResult {
  isListening: boolean;
  transcript: string;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => Promise<void>;
  clearTranscript: () => void;
}

export function useSpeechToText(): UseSpeechToTextResult {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    Voice.onSpeechResults = (e: SpeechResultsEvent) => {
      if (!mountedRef.current) {return;}
      const results = e.value ?? [];
      if (results.length > 0) {
        setTranscript(results[0]);
      }
    };

    Voice.onSpeechError = (e: SpeechErrorEvent) => {
      if (!mountedRef.current) {return;}
      setError(e.error?.message ?? 'Speech recognition error');
      setIsListening(false);
    };

    Voice.onSpeechEnd = () => {
      if (!mountedRef.current) {return;}
      setIsListening(false);
    };

    return () => {
      mountedRef.current = false;
      Voice.destroy().then(Voice.removeAllListeners);
    };
  }, []);

  const startListening = useCallback(async () => {
    setError(null);
    setTranscript('');
    try {
      await Voice.start('en-US');
      setIsListening(true);
    } catch (e) {
      setError(String(e));
      setIsListening(false);
    }
  }, []);

  const stopListening = useCallback(async () => {
    try {
      await Voice.stop();
    } catch {
      // ignore
    }
    setIsListening(false);
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscript('');
  }, []);

  return {isListening, transcript, error, startListening, stopListening, clearTranscript};
}
