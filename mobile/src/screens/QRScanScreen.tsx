/**
 * QR Scan Screen — scans a QR code to obtain track_id, then navigates to main tabs.
 *
 * QR code payload: plain string containing the track_id UUID.
 */
import React, {useCallback, useState} from 'react';
import {Alert, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import {useCameraPermission, useCameraDevice, Camera, useCodeScanner} from 'react-native-vision-camera';
import {session} from '../store/session';

interface Props {
  onSessionStarted: () => void;
}

export function QRScanScreen({onSessionStarted}: Props) {
  const {hasPermission, requestPermission} = useCameraPermission();
  const device = useCameraDevice('back');
  const [scanned, setScanned] = useState(false);

  const codeScanner = useCodeScanner({
    codeTypes: ['qr'],
    onCodeScanned: useCallback(
      async (codes) => {
        if (scanned || codes.length === 0) {
          return;
        }
        const value = codes[0].value;
        if (!value || value.trim() === '') {
          Alert.alert('Invalid QR', 'This QR code is not a valid session token.');
          return;
        }
        setScanned(true);
        await session.save(value.trim());
        onSessionStarted();
      },
      [scanned, onSessionStarted],
    ),
  });

  if (!hasPermission) {
    return (
      <View style={styles.center}>
        <Text style={styles.label}>Camera permission required</Text>
        <TouchableOpacity style={styles.button} onPress={requestPermission}>
          <Text style={styles.buttonText}>Grant Permission</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!device) {
    return (
      <View style={styles.center}>
        <Text style={styles.label}>No camera found</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Camera
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={!scanned}
        codeScanner={codeScanner}
      />
      <View style={styles.overlay}>
        <Text style={styles.hint}>Point at the session QR code</Text>
        <View style={styles.scanFrame} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#000'},
  center: {flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#111'},
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scanFrame: {
    width: 240,
    height: 240,
    borderWidth: 3,
    borderColor: '#4CAF50',
    borderRadius: 12,
    marginTop: 16,
  },
  hint: {color: '#fff', fontSize: 16, fontWeight: '600'},
  label: {color: '#fff', fontSize: 16, marginBottom: 16},
  button: {
    backgroundColor: '#4CAF50',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  buttonText: {color: '#fff', fontWeight: '700'},
});
