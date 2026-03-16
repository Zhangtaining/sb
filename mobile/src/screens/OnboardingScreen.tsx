/**
 * Session onboarding screen — shown when AI greets user at session start.
 * Displayed as a modal over the main tabs when an 'onboarding' WS event arrives.
 */
import React, {useCallback, useEffect, useState} from 'react';
import {
  ActivityIndicator,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import Tts from 'react-native-tts';
import {api} from '../api/client';
import {VoiceInputButton} from '../components/VoiceInputButton';
import {session} from '../store/session';

interface WorkoutExercise {
  name: string;
  sets: number;
  reps: string;
  recently_done?: boolean;
}

interface WorkoutPlan {
  focus_area: string;
  duration_minutes: number;
  exercises: WorkoutExercise[];
  note?: string;
}

interface Props {
  visible: boolean;
  greeting: string;
  onDismiss: (plan?: WorkoutPlan) => void;
}

export function OnboardingScreen({visible, greeting, onDismiss}: Props) {
  const [inputText, setInputText] = useState('');
  const [messages, setMessages] = useState<{role: string; content: string}[]>([]);
  const [workoutPlan, setWorkoutPlan] = useState<WorkoutPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Speak greeting on open
  useEffect(() => {
    if (visible && greeting) {
      Tts.speak(greeting);
      setMessages([{role: 'assistant', content: greeting}]);
      setWorkoutPlan(null);
      setInputText('');
    }
  }, [visible, greeting]);

  // Ensure conversation exists
  useEffect(() => {
    if (!visible) {return;}
    const personId = session.getPersonId();
    if (!personId) {return;}

    (async () => {
      try {
        const existing = session.getConversationId();
        if (existing) {
          setConversationId(existing);
          return;
        }
        const conv = await api.createConversation(personId);
        await session.setConversationId(conv.id);
        setConversationId(conv.id);
      } catch (e) {
        // conversation creation failed — will retry on send
      }
    })();
  }, [visible]);

  const handleVoiceInput = useCallback((text: string) => {
    setInputText(text);
  }, []);

  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || loading) {return;}

    setMessages(prev => [...prev, {role: 'user', content: text}]);
    setInputText('');
    setLoading(true);

    try {
      const convId = conversationId ?? session.getConversationId();
      if (!convId) {
        throw new Error('No conversation');
      }
      const result = await api.sendMessage(convId, text);
      const response = result.assistant_response;

      setMessages(prev => [...prev, {role: 'assistant', content: response}]);
      Tts.speak(response);

      // Check if response contains a workout plan (JSON in message)
      try {
        const planMatch = response.match(/```json\n?([\s\S]*?)\n?```/);
        if (planMatch) {
          const plan = JSON.parse(planMatch[1]) as WorkoutPlan;
          setWorkoutPlan(plan);
        }
      } catch {
        // no JSON plan in response
      }
    } catch {
      setMessages(prev => [
        ...prev,
        {role: 'assistant', content: "Sorry, I couldn't connect. Let's get started!"},
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = () => {
    onDismiss(workoutPlan ?? undefined);
  };

  const handleChange = () => {
    setWorkoutPlan(null);
    setInputText("Can you suggest a different workout?");
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <Text style={styles.title}>Session Start</Text>

          {/* Message history */}
          <ScrollView style={styles.messages} contentContainerStyle={styles.messagesContent}>
            {messages.map((m, i) => (
              <View
                key={i}
                style={[styles.bubble, m.role === 'user' ? styles.userBubble : styles.aiBubble]}>
                <Text style={styles.bubbleText}>{m.content}</Text>
              </View>
            ))}
            {loading && <ActivityIndicator color="#4CAF50" style={{marginTop: 8}} />}
          </ScrollView>

          {/* Workout plan card */}
          {workoutPlan && (
            <View style={styles.planCard}>
              <Text style={styles.planTitle}>
                Today's Plan — {workoutPlan.focus_area} ({workoutPlan.duration_minutes} min)
              </Text>
              {workoutPlan.exercises.map((ex, i) => (
                <Text key={i} style={styles.planExercise}>
                  • {ex.name.replace(/_/g, ' ')} — {ex.sets} sets × {ex.reps}
                  {ex.recently_done ? ' ⚠ done recently' : ''}
                </Text>
              ))}
              {workoutPlan.note && <Text style={styles.planNote}>{workoutPlan.note}</Text>}
              <View style={styles.planActions}>
                <TouchableOpacity style={styles.changeBtn} onPress={handleChange}>
                  <Text style={styles.changeBtnText}>Change it</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.acceptBtn} onPress={handleAccept}>
                  <Text style={styles.acceptBtnText}>Let's go! 💪</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Input row */}
          {!workoutPlan && (
            <View style={styles.inputRow}>
              <VoiceInputButton onTranscript={handleVoiceInput} size={44} />
              <TextInput
                style={styles.textInput}
                value={inputText}
                onChangeText={setInputText}
                placeholder="Type or speak your answer…"
                placeholderTextColor="#555"
                onSubmitEditing={handleSend}
                returnKeyType="send"
              />
              <TouchableOpacity style={styles.sendBtn} onPress={handleSend} disabled={loading}>
                <Text style={styles.sendBtnText}>Send</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Skip link */}
          <TouchableOpacity onPress={() => onDismiss()} style={styles.skipBtn}>
            <Text style={styles.skipText}>Skip for now</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#1c1c1e',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '85%',
  },
  title: {color: '#fff', fontSize: 20, fontWeight: '700', marginBottom: 12, textAlign: 'center'},
  messages: {maxHeight: 280},
  messagesContent: {paddingBottom: 8},
  bubble: {borderRadius: 12, padding: 12, marginBottom: 8, maxWidth: '85%'},
  aiBubble: {backgroundColor: '#2a2a2e', alignSelf: 'flex-start'},
  userBubble: {backgroundColor: '#4CAF50', alignSelf: 'flex-end'},
  bubbleText: {color: '#fff', fontSize: 15},
  planCard: {
    backgroundColor: '#0d1f0d',
    borderRadius: 12,
    padding: 14,
    marginVertical: 10,
    borderWidth: 1,
    borderColor: '#4CAF50',
  },
  planTitle: {color: '#4CAF50', fontWeight: '700', fontSize: 14, marginBottom: 8},
  planExercise: {color: '#ccc', fontSize: 14, marginBottom: 4},
  planNote: {color: '#888', fontSize: 12, marginTop: 6, fontStyle: 'italic'},
  planActions: {flexDirection: 'row', marginTop: 12, gap: 10},
  changeBtn: {flex: 1, borderWidth: 1, borderColor: '#555', borderRadius: 8, padding: 10, alignItems: 'center'},
  changeBtnText: {color: '#aaa', fontWeight: '600'},
  acceptBtn: {flex: 1, backgroundColor: '#4CAF50', borderRadius: 8, padding: 10, alignItems: 'center'},
  acceptBtnText: {color: '#fff', fontWeight: '700'},
  inputRow: {flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10},
  textInput: {
    flex: 1,
    backgroundColor: '#2a2a2e',
    color: '#fff',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  sendBtn: {backgroundColor: '#4CAF50', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10},
  sendBtnText: {color: '#fff', fontWeight: '700'},
  skipBtn: {alignItems: 'center', paddingVertical: 12},
  skipText: {color: '#555', fontSize: 13},
});
