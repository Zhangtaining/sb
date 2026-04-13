/**
 * Root navigator — shows QR scan until a session exists, then shows tab bar.
 */
import React, {useEffect, useRef, useState} from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {Text, View, StyleSheet} from 'react-native';
import {QRScanScreen} from '../screens/QRScanScreen';
import {HomeScreen} from '../screens/HomeScreen';
import {LiveCoachingScreen} from '../screens/LiveCoachingScreen';
import {ReplayScreen} from '../screens/ReplayScreen';
import {StatsScreen} from '../screens/StatsScreen';
import {ChatScreen} from '../screens/ChatScreen';
import {ProfileScreen} from '../screens/ProfileScreen';
import {HistoryScreen} from '../screens/HistoryScreen';
import {session} from '../store/session';
import {api} from '../api/client';

const Tab = createBottomTabNavigator();

const POLL_INTERVAL_MS = 3000;

type CameraState = 'loading' | 'offline' | 'online' | 'tracking';

function CameraStatusDot() {
  const [state, setState] = useState<CameraState>('loading');
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const status = await api.getCameraStatus();
        if (!status.camera_online) {
          setState('offline');
        } else if (status.person_detected) {
          setState('tracking');
        } else {
          setState('online');
        }
      } catch {
        setState('offline');
      }
    };

    poll();
    timerRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const DOT_COLORS: Record<CameraState, string> = {
    loading: '#555',
    offline: '#555',
    online: '#F5A623',
    tracking: '#4CAF50',
  };
  const LABELS: Record<CameraState, string> = {
    loading: 'Connecting…',
    offline: 'Camera offline',
    online: 'Not detected',
    tracking: "You're detected",
  };

  return (
    <View style={styles.cameraStatus}>
      <View style={[styles.dot, {backgroundColor: DOT_COLORS[state]}]} />
      <Text style={styles.cameraLabel}>{LABELS[state]}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  cameraStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 14,
    gap: 5,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  cameraLabel: {
    color: '#aaa',
    fontSize: 11,
  },
});

function TabIcon({label, focused}: {label: string; focused: boolean}) {
  const icons: Record<string, string> = {
    Today: '🏠',
    Live: '🎙',
    Replay: '🎬',
    Stats: '📊',
    Coach: '💬',
    Profile: '👤',
    History: '📅',
  };
  return (
    <Text style={{fontSize: 20, opacity: focused ? 1 : 0.5}}>
      {icons[label] ?? '⬜'}
    </Text>
  );
}

export function AppNavigator() {
  const [trackId, setTrackId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    session.load().then(id => {
      setTrackId(id);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return null;
  }

  if (!trackId) {
    return (
      <NavigationContainer>
        <QRScanScreen onSessionStarted={() => setTrackId(session.get())} />
      </NavigationContainer>
    );
  }

  // Screens hidden from tab bar (entered from within the exercise flow)
  const hiddenTab = {
    tabBarButton: () => null,
    tabBarItemStyle: {width: 0, overflow: 'hidden' as const},
    tabBarStyle: {display: 'none' as const},
  };

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({route}) => ({
          headerStyle: {backgroundColor: '#111'},
          headerTintColor: '#fff',
          headerRight: () => <CameraStatusDot />,
          tabBarStyle: {backgroundColor: '#1c1c1e', borderTopColor: '#333'},
          tabBarActiveTintColor: '#4CAF50',
          tabBarInactiveTintColor: '#666',
          tabBarIcon: ({focused}) => (
            <TabIcon label={route.name} focused={focused} />
          ),
        })}>
        <Tab.Screen name="Today" component={HomeScreen} />
        <Tab.Screen name="Stats" component={StatsScreen} />
        <Tab.Screen name="History" component={HistoryScreen} />
        <Tab.Screen name="Profile" component={ProfileScreen} />
        {/* Hidden screens — navigated to from within the exercise flow */}
        <Tab.Screen name="Live" component={LiveCoachingScreen} options={hiddenTab} />
        <Tab.Screen name="Coach" component={ChatScreen} options={hiddenTab} />
        <Tab.Screen name="Replay" component={ReplayScreen} options={hiddenTab} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
