import React, {useState} from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {StatusText} from '../components/StatusText';
import {PreparedSharedImage} from '../services/shareIntent';
import {colors} from '../theme/colors';

type Props = {
  image: PreparedSharedImage;
  status?: string;
  error?: string;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (description: string) => void;
};

export function ShareReviewScreen({
  image,
  status,
  error,
  submitting,
  onCancel,
  onSubmit,
}: Props) {
  const [description, setDescription] = useState('');
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Pressable
          onPress={onCancel}
          disabled={submitting}
          style={({pressed}) => [
            styles.secondaryButton,
            pressed && styles.pressed,
            submitting && styles.disabled,
          ]}>
          <Text style={styles.secondaryText}>Cancel</Text>
        </Pressable>
        <Text style={styles.title}>Review Share</Text>
      </View>

      <View style={styles.previewBox}>
        {imageFailed ? (
          <View style={styles.previewFallback}>
            <Text style={styles.previewFallbackText}>Preview failed</Text>
          </View>
        ) : (
          <Image
            source={{uri: image.previewUri}}
            style={styles.preview}
            resizeMode="contain"
            onError={() => setImageFailed(true)}
          />
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>
          {image.sourceKind === 'url' ? 'Retrieved from link' : 'Shared file'}
        </Text>
        <Text style={styles.value} numberOfLines={3}>
          {image.resolvedImageUrl || image.webUrl || image.fileName || image.contentUri}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Optional note</Text>
        <TextInput
          value={description}
          onChangeText={setDescription}
          placeholder="Add names, context, why this matters..."
          placeholderTextColor={colors.muted}
          style={styles.input}
          selectionColor={colors.blue}
          multiline
          textAlignVertical="top"
        />
      </View>

      <Pressable
        onPress={() => onSubmit(description)}
        disabled={submitting || imageFailed}
        style={({pressed}) => [
          styles.primaryButton,
          (submitting || imageFailed) && styles.disabled,
          pressed && styles.pressed,
        ]}>
        {submitting ? (
          <ActivityIndicator color={colors.paper} />
        ) : (
          <Text style={styles.primaryText}>Submit to index</Text>
        )}
      </Pressable>

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
    marginBottom: 18,
  },
  title: {
    color: colors.ink,
    fontSize: 28,
    fontWeight: '800',
  },
  previewBox: {
    alignItems: 'center',
    aspectRatio: 1,
    backgroundColor: colors.chip,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    overflow: 'hidden',
    width: '100%',
  },
  preview: {
    height: '100%',
    width: '100%',
  },
  previewFallback: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  previewFallbackText: {
    color: colors.muted,
    fontSize: 14,
  },
  section: {
    gap: 8,
    paddingTop: 18,
  },
  label: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  value: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
  },
  input: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.ink,
    fontSize: 15,
    minHeight: 96,
    paddingHorizontal: 12,
    paddingTop: 12,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.blue,
    borderRadius: 8,
    justifyContent: 'center',
    marginTop: 18,
    minHeight: 48,
  },
  primaryText: {
    color: colors.paper,
    fontSize: 15,
    fontWeight: '800',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.panel,
    borderColor: colors.blue,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 42,
    paddingHorizontal: 14,
  },
  secondaryText: {
    color: colors.blue,
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
