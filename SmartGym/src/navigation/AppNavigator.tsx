/**
 * Root navigator — shows QR scan until a session exists, then shows tab bar.
 */
import React, {useEffect, useState} from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {Text} from 'react-native';
import {QRScanScreen} from '../screens/QRScanScreen';
import {LiveCoachingScreen} from '../screens/LiveCoachingScreen';
import {ReplayScreen} from '../screens/ReplayScreen';
import {StatsScreen} from '../screens/StatsScreen';
import {ChatScreen} from '../screens/ChatScreen';
import {ProfileScreen} from '../screens/ProfileScreen';
import {HistoryScreen} from '../screens/HistoryScreen';
import {session} from '../store/session';

const Tab = createBottomTabNavigator();

function TabIcon({label, focused}: {label: string; focused: boolean}) {
  const icons: Record<string, string> = {
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

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({route}) => ({
          headerStyle: {backgroundColor: '#111'},
          headerTintColor: '#fff',
          tabBarStyle: {backgroundColor: '#1c1c1e', borderTopColor: '#333'},
          tabBarActiveTintColor: '#4CAF50',
          tabBarInactiveTintColor: '#666',
          tabBarIcon: ({focused}) => (
            <TabIcon label={route.name} focused={focused} />
          ),
        })}>
        <Tab.Screen name="Live" component={LiveCoachingScreen} />
        <Tab.Screen name="Coach" component={ChatScreen} />
        <Tab.Screen name="Replay" component={ReplayScreen} />
        <Tab.Screen name="Stats" component={StatsScreen} />
        <Tab.Screen name="History" component={HistoryScreen} />
        <Tab.Screen name="Profile" component={ProfileScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
