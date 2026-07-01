import React, {useEffect, useState} from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {FirebaseAuthTypes} from '@react-native-firebase/auth';
import {BackIconButton} from '../components/BackIconButton';
import {StatusText} from '../components/StatusText';
import {
  getSettings,
  SettingsResponse,
  saveGeminiKey,
  testHealth,
} from '../services/api';
import {
  getServerBaseUrl,
  getLocalServerUrl,
  getServerMode,
  setLocalServerUrl,
  setServerMode,
} from '../services/storage';
import {signOut} from '../services/auth';
import {colors} from '../theme/colors';

type Props = {
  user: FirebaseAuthTypes.User | null;
  onBack: () => void;
};

export function SettingsScreen({user, onBack}: Props) {
  const [apiKey, setApiKey] = useState('');
  const [geminiSet, setGeminiSet] = useState(false);
  const [useLocal, setUseLocal] = useState(false);
  const [localUrl, setLocalUrl] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [serverUrl, setServerUrl] = useState('');
  const [backendInfo, setBackendInfo] = useState<SettingsResponse['backend_info']>(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      setError('');

      try {
        const [mode, storedLocalUrl, currentServerUrl] = await Promise.all([
          getServerMode(),
          getLocalServerUrl(),
          getServerBaseUrl(),
        ]);
        if (!mounted) {
          return;
        }
        setUseLocal(mode === 'local');
        setLocalUrl(storedLocalUrl);
        setServerUrl(currentServerUrl);

        if (user) {
          try {
            const settings = await getSettings();
            if (mounted) {
              setGeminiSet(Boolean(settings.gemini_key_set));
              setBackendInfo(settings.backend_info || null);
            }
          } catch (settingsError) {
            if (mounted) {
              setError(
                settingsError instanceof Error
                  ? settingsError.message
                  : 'Unable to load account settings.',
              );
            }
          }
        }
      } catch (err) {
        if (mounted) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load local server settings.',
          );
        }
      }

      if (mounted) {
        setLoading(false);
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [user]);

  const saveKey = async () => {
    setStatus('');
    setError('');
    if (!apiKey.trim()) {
      setError('Enter an API key before saving.');
      return;
    }
    try {
      await saveGeminiKey(apiKey.trim());
      setApiKey('');
      setGeminiSet(true);
      setStatus('API key saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save API key.');
    }
  };

  const toggleServer = async (enabled: boolean) => {
    setUseLocal(enabled);
    setBackendInfo(null);
    await setServerMode(enabled ? 'local' : 'production');
    const nextUrl = await getServerBaseUrl();
    setServerUrl(nextUrl);
    setStatus(`Using ${enabled ? 'local' : 'production'} server.`);
    if (!enabled && user) {
      try {
        const settings = await getSettings();
        setGeminiSet(Boolean(settings.gemini_key_set));
        setBackendInfo(settings.backend_info || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load production settings.');
      }
    }
  };

  const chooseServer = (mode: 'local' | 'production') => {
    void toggleServer(mode === 'local');
  };

  const saveLocalUrl = async () => {
    await setLocalServerUrl(localUrl);
    const nextUrl = await getServerBaseUrl();
    setServerUrl(nextUrl);
    setStatus('Local server URL saved.');
  };

  const testServer = async () => {
    setStatus('');
    setError('');
    try {
      const ok = await testHealth();
      setStatus(ok ? 'Server is reachable.' : '');
      if (!ok) {
        setError('Server did not respond to /health.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection test failed.');
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <BackIconButton onPress={onBack} />
        <Text style={styles.title}>Settings</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Backend server</Text>
        <View style={styles.segmented}>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{selected: useLocal}}
            onPress={() => chooseServer('local')}
            style={({pressed}) => [
              styles.segment,
              useLocal && styles.segmentLocalActive,
              pressed && styles.pressed,
            ]}>
            <Text style={[styles.segmentText, useLocal && styles.segmentTextActive]}>
              Local
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{selected: !useLocal}}
            onPress={() => chooseServer('production')}
            style={({pressed}) => [
              styles.segment,
              !useLocal && styles.segmentProductionActive,
              pressed && styles.pressed,
            ]}>
            <Text style={[styles.segmentText, !useLocal && styles.segmentTextActive]}>
              Production
            </Text>
          </Pressable>
        </View>
        <Text style={styles.serverUrl}>{serverUrl || 'Server URL not loaded'}</Text>
        {useLocal ? (
          <>
            <TextInput
              value={localUrl}
              onChangeText={setLocalUrl}
              placeholder="http://127.0.0.1:5057"
              placeholderTextColor={colors.muted}
              style={styles.input}
              selectionColor={colors.yellow}
              autoCapitalize="none"
              autoCorrect={false}
            />
            <View style={styles.actions}>
              <Pressable onPress={saveLocalUrl} style={({pressed}) => [styles.secondaryButton, pressed && styles.pressed]}>
                <Text style={styles.secondaryText}>Save URL</Text>
              </Pressable>
              <Pressable onPress={testServer} style={({pressed}) => [styles.secondaryButton, pressed && styles.pressed]}>
                <Text style={styles.secondaryText}>Test server</Text>
              </Pressable>
            </View>
          </>
        ) : (
          <>
            {backendInfo ? (
              <View style={styles.readOnlyBox}>
                <Text style={styles.readOnlyLabel}>Firestore</Text>
                <Text style={styles.readOnlyValue}>
                  {backendInfo.project_id || 'Unknown project'} / {backendInfo.image_collection || 'images'}
                </Text>
                <Text style={styles.readOnlyLabel}>Cloud Storage bucket</Text>
                <Text style={styles.readOnlyValue}>
                  {backendInfo.storage_bucket || 'Not reported'}
                </Text>
                <Text style={styles.readOnlyLabel}>Vector search</Text>
                <Text style={styles.readOnlyValue}>
                  {backendInfo.vector_search_enabled ? 'Enabled' : 'Disabled'}
                  {backendInfo.vector_field ? ` - ${backendInfo.vector_field}` : ''}
                  {backendInfo.vector_search_fallback ? ' - fallback on' : ''}
                </Text>
              </View>
            ) : null}
            <Pressable onPress={testServer} style={({pressed}) => [styles.secondaryButton, pressed && styles.pressed]}>
              <Text style={styles.secondaryText}>Test server</Text>
            </Pressable>
          </>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Signed in</Text>
        <Text style={styles.value}>
          {user
            ? [user.displayName, user.email].filter(Boolean).join(' - ')
            : loading
              ? 'Loading...'
              : 'Not signed in'}
        </Text>
        {user ? (
          <Pressable onPress={signOut} style={({pressed}) => [styles.secondaryButton, pressed && styles.pressed]}>
            <Text style={styles.secondaryText}>Sign out</Text>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Gemini API key</Text>
        <TextInput
          value={apiKey}
          onChangeText={setApiKey}
          placeholder={geminiSet ? 'Key saved' : 'AIza...'}
          placeholderTextColor={colors.muted}
          style={styles.input}
          selectionColor={colors.yellow}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
        />
        <Pressable
          onPress={saveKey}
          disabled={!user}
          style={({pressed}) => [
            styles.primaryButton,
            !user && styles.disabled,
            pressed && styles.pressed,
          ]}>
          <Text style={styles.primaryText}>Save key</Text>
        </Pressable>
      </View>

      <StatusText message={status} tone="good" />
      <StatusText message={error} tone="bad" />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.paper,
    flexGrow: 1,
    padding: 20,
    paddingTop: 48,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    marginBottom: 22,
  },
  title: {
    color: colors.ink,
    fontSize: 30,
    fontWeight: '800',
  },
  section: {
    borderBottomColor: colors.line,
    borderBottomWidth: 1,
    gap: 10,
    paddingBottom: 18,
    paddingTop: 16,
  },
  label: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  value: {
    color: colors.muted,
    fontSize: 15,
  },
  serverUrl: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 4,
  },
  readOnlyBox: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    gap: 5,
    padding: 12,
  },
  readOnlyLabel: {
    color: colors.ink,
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  readOnlyValue: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 4,
  },
  input: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.ink,
    fontSize: 15,
    minHeight: 48,
    paddingHorizontal: 12,
  },
  actions: {
    flexDirection: 'row',
    gap: 10,
  },
  segmented: {
    backgroundColor: colors.chip,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    padding: 3,
  },
  segment: {
    alignItems: 'center',
    borderRadius: 6,
    flex: 1,
    minHeight: 42,
    justifyContent: 'center',
  },
  segmentLocalActive: {
    backgroundColor: colors.yellow,
  },
  segmentProductionActive: {
    backgroundColor: colors.green,
  },
  segmentText: {
    color: colors.ink,
    fontSize: 14,
    fontWeight: '800',
  },
  segmentTextActive: {
    color: colors.paper,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.ink,
    borderRadius: 8,
    minHeight: 46,
    justifyContent: 'center',
  },
  primaryText: {
    color: colors.paper,
    fontSize: 15,
    fontWeight: '800',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 42,
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  secondaryText: {
    color: colors.ink,
    fontSize: 14,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.72,
  },
  disabled: {
    opacity: 0.45,
  },
});
