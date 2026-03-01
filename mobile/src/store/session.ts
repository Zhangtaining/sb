/**
 * Simple in-memory + AsyncStorage session store.
 * Holds the track_id obtained from the QR code scan.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY_TRACK_ID = '@smartgym/track_id';

let _trackId: string | null = null;

export const session = {
  async load(): Promise<string | null> {
    if (_trackId) {
      return _trackId;
    }
    _trackId = await AsyncStorage.getItem(KEY_TRACK_ID);
    return _trackId;
  },

  async save(trackId: string): Promise<void> {
    _trackId = trackId;
    await AsyncStorage.setItem(KEY_TRACK_ID, trackId);
  },

  async clear(): Promise<void> {
    _trackId = null;
    await AsyncStorage.removeItem(KEY_TRACK_ID);
  },

  get(): string | null {
    return _trackId;
  },
};
