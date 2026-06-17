import React, {useEffect, useRef, useState} from 'react';
import {SafeAreaView, StatusBar, StyleSheet} from 'react-native';
import {FirebaseAuthTypes} from '@react-native-firebase/auth';
import {colors} from './theme/colors';
import {onAuthChanged, signInWithGoogle} from './services/auth';
import {CropRect} from './services/api';
import {
  PreparedSharedImage,
  SharedImage,
  listenForSharedImages,
  prepareSharedImage,
  uploadSharedImage,
} from './services/shareIntent';
import {LoginScreen} from './screens/LoginScreen';
import {QueryScreen} from './screens/QueryScreen';
import {SettingsScreen} from './screens/SettingsScreen';
import {ShareReviewScreen} from './screens/ShareReviewScreen';
import {ProfileScreen} from './screens/ProfileScreen';

type Screen = 'login' | 'query' | 'settings' | 'profile' | 'shareReview';

export default function App() {
  const [user, setUser] = useState<FirebaseAuthTypes.User | null>(null);
  const [screen, setScreen] = useState<Screen>('login');
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [shareStatus, setShareStatus] = useState('');
  const [shareError, setShareError] = useState('');
  const [pendingShare, setPendingShare] = useState<PreparedSharedImage | null>(
    null,
  );
  const [shareSubmitting, setShareSubmitting] = useState(false);
  const lastShareKeyRef = useRef('');

  useEffect(() => {
    return onAuthChanged(currentUser => {
      setUser(currentUser);
      setScreen(currentUser ? 'query' : 'login');
    });
  }, []);

  useEffect(() => {
    return listenForSharedImages(handleSharedImage, setShareStatus);
  }, [user]);

  const handleLogin = async () => {
    setLoginBusy(true);
    setLoginError('');
    try {
      await signInWithGoogle();
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Google login failed.');
    } finally {
      setLoginBusy(false);
    }
  };

  const handleSharedImage = async (image: SharedImage) => {
    if (!user) {
      setShareStatus('Sign in before sharing images into Source Bruh.');
      setScreen('login');
      return;
    }

    const shareKey = image.contentUri || image.webUrl || image.text || '';
    if (shareKey && shareKey === lastShareKeyRef.current && pendingShare) {
      setScreen('shareReview');
      return;
    }
    lastShareKeyRef.current = shareKey;

    setShareStatus('Retrieving shared image...');
    setShareError('');
    try {
      const prepared = await prepareSharedImage(image);
      setPendingShare(prepared);
      setShareStatus(
        prepared.sourceKind === 'url'
          ? 'Backend retrieved the image. Review before indexing.'
          : 'Review the shared image before indexing.',
      );
      setScreen('shareReview');
    } catch (err) {
      setShareError(
        err instanceof Error
          ? err.message
          : 'Could not retrieve the shared image.',
      );
      setShareStatus('');
      setScreen('query');
    }
  };

  const handleSubmitShare = async (
    description: string,
    cropRect?: CropRect | null,
  ) => {
    if (!pendingShare) {
      return;
    }
    setShareSubmitting(true);
    setShareStatus('Indexing shared image...');
    setShareError('');
    try {
      await uploadSharedImage(pendingShare, description, cropRect);
      setPendingShare(null);
      setShareStatus('Shared image indexed.');
      setScreen('query');
    } catch (err) {
      setShareError(
        err instanceof Error ? err.message : 'Could not index shared image.',
      );
    } finally {
      setShareSubmitting(false);
    }
  };

  const handleCancelShare = () => {
    setPendingShare(null);
    setShareStatus('Shared image was not indexed.');
    setShareError('');
    setScreen(user ? 'query' : 'login');
  };

  if (screen === 'shareReview' && pendingShare) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <StatusBar barStyle="dark-content" backgroundColor={colors.paper} />
        <ShareReviewScreen
          image={pendingShare}
          status={shareStatus}
          error={shareError}
          submitting={shareSubmitting}
          onCancel={handleCancelShare}
          onSubmit={handleSubmitShare}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" backgroundColor={colors.paper} />
      {screen === 'settings' ? (
        <SettingsScreen
          user={user}
          onBack={() => setScreen(user ? 'query' : 'login')}
        />
      ) : screen === 'profile' ? (
        <ProfileScreen
          user={user}
          onBack={() => setScreen(user ? 'query' : 'login')}
        />
      ) : user && screen === 'query' ? (
        <QueryScreen
          onSettings={() => setScreen('settings')}
          onProfile={() => setScreen('profile')}
          shareStatus={shareStatus}
          shareError={shareError}
        />
      ) : (
        <LoginScreen
          onLogin={handleLogin}
          onSettings={() => setScreen('settings')}
          loading={loginBusy}
          message={loginError || shareError || shareStatus}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: colors.paper,
    flex: 1,
  },
});
