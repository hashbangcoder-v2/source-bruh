import React, {useEffect, useMemo, useRef, useState} from 'react';
import {
  ActivityIndicator,
  Image,
  LayoutChangeEvent,
  PanResponder,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {StatusText} from '../components/StatusText';
import {CropRect} from '../services/api';
import {PreparedSharedImage} from '../services/shareIntent';
import {colors} from '../theme/colors';

type Props = {
  image: PreparedSharedImage;
  status?: string;
  error?: string;
  submitting?: boolean;
  onCancel: () => void;
  onSubmit: (description: string, cropRect?: CropRect | null) => void;
};

type Size = {
  width: number;
  height: number;
};

const DEFAULT_CROP: CropRect = {x: 0.1, y: 0.1, width: 0.8, height: 0.8};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function clampCrop(rect: CropRect): CropRect {
  const width = clamp(rect.width, 0.08, 1);
  const height = clamp(rect.height, 0.08, 1);
  return {
    width,
    height,
    x: clamp(rect.x, 0, 1 - width),
    y: clamp(rect.y, 0, 1 - height),
  };
}

function imageFrame(container: Size, imageSize: Size) {
  if (!container.width || !container.height || !imageSize.width || !imageSize.height) {
    return {left: 0, top: 0, width: container.width, height: container.height};
  }
  const containerRatio = container.width / container.height;
  const imageRatio = imageSize.width / imageSize.height;
  if (imageRatio > containerRatio) {
    const height = container.width / imageRatio;
    return {
      left: 0,
      top: (container.height - height) / 2,
      width: container.width,
      height,
    };
  }
  const width = container.height * imageRatio;
  return {
    left: (container.width - width) / 2,
    top: 0,
    width,
    height: container.height,
  };
}

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
  const [cropMode, setCropMode] = useState(false);
  const [cropRect, setCropRect] = useState<CropRect | null>(null);
  const [previewSize, setPreviewSize] = useState<Size>({width: 0, height: 0});
  const [imageSize, setImageSize] = useState<Size>({width: 1, height: 1});
  const gestureStart = useRef<CropRect>(DEFAULT_CROP);

  useEffect(() => {
    Image.getSize(
      image.previewUri,
      (width, height) => setImageSize({width, height}),
      () => setImageSize({width: 1, height: 1}),
    );
  }, [image.previewUri]);

  const frame = imageFrame(previewSize, imageSize);
  const activeCrop = cropRect || DEFAULT_CROP;
  const cropBox = {
    left: frame.left + activeCrop.x * frame.width,
    top: frame.top + activeCrop.y * frame.height,
    width: activeCrop.width * frame.width,
    height: activeCrop.height * frame.height,
  };

  const moveResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => cropMode,
        onMoveShouldSetPanResponder: () => cropMode,
        onPanResponderGrant: () => {
          gestureStart.current = activeCrop;
        },
        onPanResponderMove: (_, gesture) => {
          if (!frame.width || !frame.height) {
            return;
          }
          setCropRect(
            clampCrop({
              ...gestureStart.current,
              x: gestureStart.current.x + gesture.dx / frame.width,
              y: gestureStart.current.y + gesture.dy / frame.height,
            }),
          );
        },
      }),
    [activeCrop, cropMode, frame.height, frame.width],
  );

  const resizeResponder = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => cropMode,
        onMoveShouldSetPanResponder: () => cropMode,
        onPanResponderGrant: () => {
          gestureStart.current = activeCrop;
        },
        onPanResponderMove: (_, gesture) => {
          if (!frame.width || !frame.height) {
            return;
          }
          setCropRect(
            clampCrop({
              ...gestureStart.current,
              width: gestureStart.current.width + gesture.dx / frame.width,
              height: gestureStart.current.height + gesture.dy / frame.height,
            }),
          );
        },
      }),
    [activeCrop, cropMode, frame.height, frame.width],
  );

  const onPreviewLayout = (event: LayoutChangeEvent) => {
    const {width, height} = event.nativeEvent.layout;
    setPreviewSize({width, height});
  };

  const startCrop = () => {
    setCropRect(current => current || DEFAULT_CROP);
    setCropMode(true);
  };

  const submitCrop = () => {
    setCropRect(clampCrop(activeCrop));
    setCropMode(false);
  };

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Pressable
          onPress={onCancel}
          disabled={submitting}
          style={({pressed}) => [
            styles.backButton,
            pressed && styles.pressed,
            submitting && styles.disabled,
          ]}>
          <Text style={styles.backText}>Back</Text>
        </Pressable>
        <Text style={styles.title}>Review Share</Text>
      </View>

      <View style={styles.previewBox} onLayout={onPreviewLayout}>
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
        {cropMode ? (
          <>
            <View style={styles.cropShade} pointerEvents="none" />
            <View
              {...moveResponder.panHandlers}
              style={[styles.cropBox, cropBox]}>
              <View
                {...resizeResponder.panHandlers}
                style={styles.cropHandle}
              />
            </View>
          </>
        ) : null}
      </View>

      <View style={styles.cropActions}>
        {cropMode ? (
          <>
            <Pressable
              onPress={() => setCropRect(DEFAULT_CROP)}
              style={({pressed}) => [styles.neutralButton, pressed && styles.pressed]}>
              <Text style={styles.neutralText}>Reset</Text>
            </Pressable>
            <Pressable
              onPress={submitCrop}
              style={({pressed}) => [styles.cropButton, pressed && styles.pressed]}>
              <Text style={styles.cropButtonText}>Confirm Crop</Text>
            </Pressable>
          </>
        ) : (
          <Pressable
            onPress={startCrop}
            disabled={imageFailed || submitting}
            style={({pressed}) => [
              styles.neutralButton,
              (imageFailed || submitting) && styles.disabled,
              pressed && styles.pressed,
            ]}>
            <Text style={styles.neutralText}>{cropRect ? 'Edit crop' : 'Crop'}</Text>
          </Pressable>
        )}
      </View>

      {cropRect && !cropMode ? (
        <Text style={styles.cropApplied}>Crop will be applied before indexing.</Text>
      ) : null}

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
          selectionColor={colors.yellow}
          multiline
          textAlignVertical="top"
        />
      </View>

      <Pressable
        onPress={() => onSubmit(description, cropRect)}
        disabled={submitting || imageFailed || cropMode}
        style={({pressed}) => [
          styles.primaryButton,
          (submitting || imageFailed || cropMode) && styles.disabled,
          pressed && styles.pressed,
        ]}>
        {submitting ? (
          <ActivityIndicator color={colors.paper} />
        ) : (
          <Text style={styles.primaryText}>Add to index</Text>
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
    position: 'relative',
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
  cropShade: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(21,21,18,0.24)',
  },
  cropBox: {
    borderColor: colors.yellow,
    borderWidth: 3,
    position: 'absolute',
  },
  cropHandle: {
    backgroundColor: colors.yellow,
    bottom: -10,
    height: 22,
    position: 'absolute',
    right: -10,
    width: 22,
  },
  cropActions: {
    flexDirection: 'row',
    gap: 10,
    paddingTop: 12,
  },
  cropApplied: {
    color: colors.muted,
    fontSize: 12,
    paddingTop: 8,
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
    backgroundColor: colors.green,
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
  backButton: {
    alignItems: 'center',
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 34,
    paddingHorizontal: 12,
  },
  backText: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '700',
  },
  neutralButton: {
    alignItems: 'center',
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 40,
    paddingHorizontal: 14,
  },
  neutralText: {
    color: colors.ink,
    fontSize: 14,
    fontWeight: '700',
  },
  cropButton: {
    alignItems: 'center',
    backgroundColor: colors.yellow,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 40,
    paddingHorizontal: 14,
  },
  cropButtonText: {
    color: colors.ink,
    fontSize: 14,
    fontWeight: '800',
  },
  pressed: {
    opacity: 0.72,
  },
  disabled: {
    opacity: 0.45,
  },
});
