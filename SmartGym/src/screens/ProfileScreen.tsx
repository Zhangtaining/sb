/**
 * Profile tab — view and edit goals, injury notes, preferences.
 */
import React, {useEffect, useState} from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import {session} from '../store/session';

const GOAL_OPTIONS = [
  {key: 'strength', label: 'Strength'},
  {key: 'weight_loss', label: 'Weight Loss'},
  {key: 'muscle_gain', label: 'Muscle Gain'},
  {key: 'endurance', label: 'Endurance'},
  {key: 'flexibility', label: 'Flexibility'},
];

interface Profile {
  name: string;
  goals: string[];
  injury_notes: string;
  member_since: string;
}

export function ProfileScreen() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [goals, setGoals] = useState<string[]>([]);
  const [injuryNotes, setInjuryNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const personId = session.getPersonId();

  useEffect(() => {
    if (!personId) {
      setLoading(false);
      return;
    }

    // Fetch profile from API
    fetch(`http://localhost:8000/persons/${personId}`)
      .then(r => r.json())
      .then((data: Profile) => {
        setProfile(data);
        setGoals(data.goals ?? []);
        setInjuryNotes(data.injury_notes ?? '');
      })
      .catch(() => {
        // Server may not be running — show defaults
        setProfile({name: 'You', goals: [], injury_notes: '', member_since: ''});
      })
      .finally(() => setLoading(false));
  }, [personId]);

  const toggleGoal = (key: string) => {
    setGoals(prev =>
      prev.includes(key) ? prev.filter(g => g !== key) : [...prev, key],
    );
  };

  const handleSave = async () => {
    if (!personId) {return;}
    setSaving(true);
    try {
      await fetch(`http://localhost:8000/persons/${personId}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({goals, injury_notes: injuryNotes}),
      });
      Alert.alert('Saved', 'Profile updated successfully.');
    } catch {
      Alert.alert('Error', 'Could not save — check server connection.');
    } finally {
      setSaving(false);
    }
  };

  const handleSignOut = () => {
    Alert.alert('Sign Out', 'This will clear your session. Continue?', [
      {text: 'Cancel', style: 'cancel'},
      {
        text: 'Sign Out',
        style: 'destructive',
        onPress: async () => {
          await session.clear();
          // Navigate back to QR screen happens automatically via AppNavigator
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#4CAF50" size="large" />
      </View>
    );
  }

  if (!personId) {
    return (
      <View style={styles.center}>
        <Text style={styles.noPersonText}>
          No profile linked.{'\n'}Register via CLI and scan the QR code.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Name */}
      {profile && (
        <View style={styles.section}>
          <Text style={styles.label}>Name</Text>
          <Text style={styles.nameText}>{profile.name}</Text>
          {profile.member_since ? (
            <Text style={styles.subText}>Member since {profile.member_since}</Text>
          ) : null}
        </View>
      )}

      {/* Goals */}
      <View style={styles.section}>
        <Text style={styles.label}>Fitness Goals</Text>
        {GOAL_OPTIONS.map(opt => (
          <View key={opt.key} style={styles.goalRow}>
            <Text style={styles.goalLabel}>{opt.label}</Text>
            <Switch
              value={goals.includes(opt.key)}
              onValueChange={() => toggleGoal(opt.key)}
              trackColor={{true: '#4CAF50', false: '#333'}}
              thumbColor="#fff"
            />
          </View>
        ))}
      </View>

      {/* Injury notes */}
      <View style={styles.section}>
        <Text style={styles.label}>Injury / Limitation Notes</Text>
        <TextInput
          style={styles.notesInput}
          value={injuryNotes}
          onChangeText={setInjuryNotes}
          placeholder="e.g. left knee strain, avoid overhead press"
          placeholderTextColor="#555"
          multiline
          numberOfLines={3}
        />
        <Text style={styles.hint}>
          The AI trainer uses these notes to tailor recommendations.
        </Text>
      </View>

      {/* Save button */}
      <TouchableOpacity
        style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
        onPress={handleSave}
        disabled={saving}>
        {saving ? (
          <ActivityIndicator color="#fff" size="small" />
        ) : (
          <Text style={styles.saveBtnText}>Save Changes</Text>
        )}
      </TouchableOpacity>

      {/* Sign out */}
      <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#111'},
  content: {padding: 20, paddingBottom: 40},
  center: {flex: 1, backgroundColor: '#111', alignItems: 'center', justifyContent: 'center', padding: 24},
  noPersonText: {color: '#888', textAlign: 'center', fontSize: 15, lineHeight: 24},
  section: {marginBottom: 28},
  label: {color: '#aaa', fontSize: 12, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 10},
  nameText: {color: '#fff', fontSize: 22, fontWeight: '700'},
  subText: {color: '#555', fontSize: 13, marginTop: 4},
  goalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#222',
  },
  goalLabel: {color: '#fff', fontSize: 16},
  notesInput: {
    backgroundColor: '#1c1c1e',
    color: '#fff',
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    textAlignVertical: 'top',
    minHeight: 80,
  },
  hint: {color: '#555', fontSize: 12, marginTop: 6},
  saveBtn: {
    backgroundColor: '#4CAF50',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 16,
  },
  saveBtnDisabled: {opacity: 0.6},
  saveBtnText: {color: '#fff', fontSize: 16, fontWeight: '700'},
  signOutBtn: {
    borderWidth: 1,
    borderColor: '#c0392b',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  signOutText: {color: '#c0392b', fontSize: 16, fontWeight: '600'},
});
