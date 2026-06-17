import React from 'react';
import {Pressable, StyleSheet, Text, ViewStyle} from 'react-native';
import {colors} from '../theme/colors';

type Props = {
  onPress: () => void;
  disabled?: boolean;
  light?: boolean;
  style?: ViewStyle;
};

export function BackIconButton({onPress, disabled, light, style}: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Back"
      disabled={disabled}
      onPress={onPress}
      style={({pressed}) => [
        styles.button,
        light && styles.buttonLight,
        pressed && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}>
      <Text style={[styles.icon, light && styles.iconLight]}>‹</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    height: 42,
    justifyContent: 'center',
    width: 42,
  },
  buttonLight: {
    backgroundColor: 'rgba(251,250,246,0.16)',
    borderColor: 'rgba(251,250,246,0.22)',
  },
  disabled: {
    opacity: 0.45,
  },
  icon: {
    color: colors.ink,
    fontSize: 32,
    fontWeight: '600',
    lineHeight: 34,
    marginTop: -2,
  },
  iconLight: {
    color: colors.paper,
  },
  pressed: {
    opacity: 0.72,
  },
});
