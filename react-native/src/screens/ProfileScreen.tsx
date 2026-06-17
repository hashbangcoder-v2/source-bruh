import React, {useEffect, useState} from 'react';
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {FirebaseAuthTypes} from '@react-native-firebase/auth';
import {BackIconButton} from '../components/BackIconButton';
import {StatusText} from '../components/StatusText';
import {ProfileResponse, getProfile} from '../services/api';
import {colors} from '../theme/colors';

type Props = {
  user: FirebaseAuthTypes.User | null;
  onBack: () => void;
};

function StatBlock({label, value}: {label: string; value: number}) {
  return (
    <View style={styles.statBlock}>
      <Text style={styles.statValue}>{value.toLocaleString()}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

export function ProfileScreen({user, onBack}: Props) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!user) {
        return;
      }
      setLoading(true);
      setError('');
      try {
        const nextProfile = await getProfile();
        if (mounted) {
          setProfile(nextProfile);
        }
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Unable to load profile.');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, [user]);

  const name = profile?.name || user?.displayName || 'Source Bruh user';
  const email = profile?.email || user?.email || '';
  const photoUrl = profile?.photo_url || user?.photoURL || '';
  const stats = profile?.stats || {
    files_indexed: 0,
    queries_last_week: 0,
    queries_lifetime: 0,
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <BackIconButton onPress={onBack} />
      </View>

      <View style={styles.identity}>
        {photoUrl ? (
          <Image source={{uri: photoUrl}} style={styles.avatar} />
        ) : (
          <View style={styles.avatarFallback}>
            <Text style={styles.avatarInitial}>{name.trim().slice(0, 1).toUpperCase()}</Text>
          </View>
        )}
        <Text style={styles.name}>{name}</Text>
        {email ? <Text style={styles.email}>{email}</Text> : null}
      </View>

      {loading ? <ActivityIndicator color={colors.ink} /> : null}
      <StatusText message={error} tone="bad" />

      <View style={styles.statsGrid}>
        <StatBlock label="files indexed" value={stats.files_indexed} />
        <StatBlock label="queries this week" value={stats.queries_last_week} />
        <StatBlock label="queries lifetime" value={stats.queries_lifetime} />
      </View>
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
    marginBottom: 42,
  },
  identity: {
    alignItems: 'center',
    gap: 8,
    justifyContent: 'center',
    marginBottom: 44,
  },
  avatar: {
    borderRadius: 58,
    height: 116,
    width: 116,
  },
  avatarFallback: {
    alignItems: 'center',
    backgroundColor: colors.chip,
    borderColor: colors.line,
    borderRadius: 58,
    borderWidth: 1,
    height: 116,
    justifyContent: 'center',
    width: 116,
  },
  avatarInitial: {
    color: colors.ink,
    fontSize: 42,
    fontWeight: '800',
  },
  name: {
    color: colors.ink,
    fontSize: 24,
    fontWeight: '800',
    marginTop: 8,
    textAlign: 'center',
  },
  email: {
    color: colors.muted,
    fontSize: 15,
    textAlign: 'center',
  },
  statsGrid: {
    borderTopColor: colors.line,
    borderTopWidth: 1,
    gap: 16,
    paddingTop: 20,
  },
  statBlock: {
    alignItems: 'center',
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    padding: 18,
  },
  statValue: {
    color: colors.ink,
    fontSize: 30,
    fontWeight: '800',
  },
  statLabel: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '700',
    marginTop: 4,
    textTransform: 'uppercase',
  },
});
