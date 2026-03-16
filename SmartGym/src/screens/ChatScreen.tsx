/**
 * Chat tab — full conversational interface with the AI trainer.
 * Supports voice input (STT) and text input. AI responses spoken via TTS.
 */
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import Tts from 'react-native-tts';
import {api, MessageResponse} from '../api/client';
import {VoiceInputButton} from '../components/VoiceInputButton';
import {session} from '../store/session';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  id: string;
}

export function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);
  const listRef = useRef<FlatList>(null);

  // Initialize conversation on mount
  useEffect(() => {
    (async () => {
      const personId = session.getPersonId();
      if (!personId) {
        setInitialized(true);
        return;
      }

      try {
        // Get or create conversation
        let convId = session.getConversationId();
        if (!convId) {
          const conv = await api.createConversation(personId);
          convId = conv.id;
          await session.setConversationId(convId);
        }
        setConversationId(convId);

        // Load existing message history
        const history = await api.getMessages(convId);
        const mapped: Message[] = history
          .filter(m => m.role !== 'system')
          .map((m, i) => ({
            role: m.role as 'user' | 'assistant',
            content: m.content,
            id: `hist-${i}`,
          }));
        setMessages(mapped);
      } catch {
        // start fresh if API unavailable
      } finally {
        setInitialized(true);
      }
    })();
  }, []);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => listRef.current?.scrollToEnd({animated: true}), 100);
  }, []);

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages.length, scrollToBottom]);

  const handleSend = async (text?: string) => {
    const msgText = (text ?? inputText).trim();
    if (!msgText || loading) {return;}

    setInputText('');
    const userMsg: Message = {role: 'user', content: msgText, id: Date.now().toString()};
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const personId = session.getPersonId();
      let convId = conversationId;

      // Create conversation if needed
      if (!convId && personId) {
        const conv = await api.createConversation(personId);
        convId = conv.id;
        await session.setConversationId(convId);
        setConversationId(convId);
      }

      if (!convId) {
        throw new Error('No conversation available');
      }

      const result = await api.sendMessage(convId, msgText);
      const assistantMsg: Message = {
        role: 'assistant',
        content: result.assistant_response,
        id: (Date.now() + 1).toString(),
      };
      setMessages(prev => [...prev, assistantMsg]);
      Tts.speak(result.assistant_response);
    } catch {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: "I couldn't connect right now. Make sure the gym server is running.",
          id: (Date.now() + 1).toString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleVoice = useCallback((transcript: string) => {
    setInputText(transcript);
  }, []);

  if (!initialized) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#4CAF50" size="large" />
      </View>
    );
  }

  const personId = session.getPersonId();
  if (!personId) {
    return (
      <View style={styles.center}>
        <Text style={styles.noPersonText}>
          No profile linked yet.{'\n'}Register a person with the CLI and scan the QR code.
        </Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}>

      {/* Message list */}
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={item => item.id}
        style={styles.list}
        contentContainerStyle={styles.listContent}
        renderItem={({item}) => (
          <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.aiBubble]}>
            <Text style={styles.bubbleText}>{item.content}</Text>
          </View>
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>Ask your AI trainer anything!</Text>
            <Text style={styles.emptyHint}>
              "What should I work on today?"{'\n'}
              "How are my squats trending?"{'\n'}
              "I have 30 minutes, what's a good workout?"
            </Text>
          </View>
        }
      />

      {loading && (
        <View style={styles.typingRow}>
          <ActivityIndicator color="#4CAF50" size="small" />
          <Text style={styles.typingText}>Trainer is thinking…</Text>
        </View>
      )}

      {/* Input row */}
      <View style={styles.inputRow}>
        <VoiceInputButton onTranscript={handleVoice} size={44} />
        <TextInput
          style={styles.textInput}
          value={inputText}
          onChangeText={setInputText}
          placeholder="Ask your trainer…"
          placeholderTextColor="#555"
          onSubmitEditing={() => handleSend()}
          returnKeyType="send"
          multiline
        />
        <TouchableOpacity
          style={[styles.sendBtn, (!inputText.trim() || loading) && styles.sendBtnDisabled]}
          onPress={() => handleSend()}
          disabled={!inputText.trim() || loading}>
          <Text style={styles.sendBtnText}>↑</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},
  center: {flex: 1, backgroundColor: '#111', alignItems: 'center', justifyContent: 'center', padding: 24},
  noPersonText: {color: '#888', textAlign: 'center', fontSize: 15, lineHeight: 24},
  list: {flex: 1},
  listContent: {padding: 16, paddingBottom: 8},
  bubble: {borderRadius: 16, padding: 12, marginBottom: 8, maxWidth: '80%'},
  aiBubble: {backgroundColor: '#1c1c1e', alignSelf: 'flex-start'},
  userBubble: {backgroundColor: '#4CAF50', alignSelf: 'flex-end'},
  bubbleText: {color: '#fff', fontSize: 15, lineHeight: 22},
  emptyContainer: {alignItems: 'center', marginTop: 60},
  emptyText: {color: '#aaa', fontSize: 16, fontWeight: '600', marginBottom: 16},
  emptyHint: {color: '#555', fontSize: 14, textAlign: 'center', lineHeight: 24},
  typingRow: {flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 4, gap: 8},
  typingText: {color: '#555', fontSize: 13},
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: '#222',
    backgroundColor: '#111',
  },
  textInput: {
    flex: 1,
    backgroundColor: '#1c1c1e',
    color: '#fff',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 100,
  },
  sendBtn: {
    backgroundColor: '#4CAF50',
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {backgroundColor: '#333'},
  sendBtnText: {color: '#fff', fontSize: 18, fontWeight: '700'},
});
