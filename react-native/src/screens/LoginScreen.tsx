import React from 'react';
import {
  Image,
  ImageBackground,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {colors} from '../theme/colors';

type Props = {
  onLogin: () => void;
  onSettings: () => void;
  loading?: boolean;
  message?: string;
};

export function LoginScreen({onLogin, onSettings, loading, message}: Props) {
  return (
    <ImageBackground
      source={require('../../assets/icon.png')}
      resizeMode="cover"
      blurRadius={10}
      style={styles.background}>
      <View style={styles.overlay}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Settings"
          onPress={onSettings}
          style={styles.settings}>
          <Text style={styles.settingsText}>Settings</Text>
        </Pressable>
        <View style={styles.brand}>
          <Image source={require('../../assets/icon.png')} style={styles.icon} />
          <Text style={styles.title}>Source Bruh</Text>
          <Text style={styles.subtitle}>Find the image before the thread vanishes.</Text>
        </View>
        <Pressable
          accessibilityRole="button"
          disabled={loading}
          onPress={onLogin}
          style={({pressed}) => [
            styles.loginButton,
            pressed && styles.pressed,
            loading && styles.disabled,
          ]}>
          <Text style={styles.loginText}>
            {loading ? 'Signing in...' : 'Login With Google'}
          </Text>
        </Pressable>
        {message ? <Text style={styles.message}>{message}</Text> : null}
      </View>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  background: {
    flex: 1,
  },
  overlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(251,250,246,0.84)',
    flex: 1,
    justifyContent: 'space-between',
    padding: 24,
    paddingBottom: 42,
    paddingTop: 54,
  },
  settings: {
    alignItems: 'center',
    alignSelf: 'flex-end',
    backgroundColor: colors.ink,
    borderRadius: 8,
    height: 42,
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  settingsText: {
    color: colors.paper,
    fontSize: 13,
    fontWeight: '800',
  },
  brand: {
    alignItems: 'center',
    gap: 16,
  },
  icon: {
    borderRadius: 28,
    height: 112,
    width: 112,
  },
  title: {
    color: colors.ink,
    fontSize: 36,
    fontWeight: '800',
    textAlign: 'center',
  },
  subtitle: {
    color: colors.muted,
    fontSize: 16,
    lineHeight: 22,
    maxWidth: 280,
    textAlign: 'center',
  },
  loginButton: {
    alignItems: 'center',
    backgroundColor: colors.ink,
    borderRadius: 8,
    height: 54,
    justifyContent: 'center',
    width: '100%',
  },
  loginText: {
    color: colors.paper,
    fontSize: 16,
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.55,
  },
  message: {
    color: colors.red,
    fontSize: 13,
    marginTop: 14,
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.78,
  },
});
