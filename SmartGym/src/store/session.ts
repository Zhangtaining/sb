/**
 * Simple in-memory + AsyncStorage session store.
 * Holds track_id, person_id, and conversation_id.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_TRACK_ID = '@smartgym/track_id';
const KEY_PERSON_ID = '@smartgym/person_id';
const KEY_CONVERSATION_ID = '@smartgym/conversation_id';

let _trackId: string | null = null;
let _personId: string | null = null;
let _conversationId: string | null = null;
let _exerciseTarget: string | null = null; // e.g. "10-15"

export const session = {
  async load(): Promise<string | null> {
    if (_trackId) {
      return _trackId;
    }
    [_trackId, _personId, _conversationId] = await Promise.all([
      AsyncStorage.getItem(KEY_TRACK_ID),
      AsyncStorage.getItem(KEY_PERSON_ID),
      AsyncStorage.getItem(KEY_CONVERSATION_ID),
    ]);
    return _trackId;
  },

  async save(trackId: string, personId?: string): Promise<void> {
    _trackId = trackId;
    _personId = personId ?? null;
    await AsyncStorage.setItem(KEY_TRACK_ID, trackId);
    if (personId) {
      await AsyncStorage.setItem(KEY_PERSON_ID, personId);
    }
  },

  async setConversationId(id: string): Promise<void> {
    _conversationId = id;
    await AsyncStorage.setItem(KEY_CONVERSATION_ID, id);
  },

  async clear(): Promise<void> {
    _trackId = null;
    _personId = null;
    _conversationId = null;
    await AsyncStorage.multiRemove([KEY_TRACK_ID, KEY_PERSON_ID, KEY_CONVERSATION_ID]);
  },

  get(): string | null {
    return _trackId;
  },

  getPersonId(): string | null {
    return _personId;
  },

  getConversationId(): string | null {
    return _conversationId;
  },

  setExerciseTarget(reps: string): void {
    _exerciseTarget = reps;
  },

  getExerciseTarget(): string | null {
    return _exerciseTarget;
  },
};
