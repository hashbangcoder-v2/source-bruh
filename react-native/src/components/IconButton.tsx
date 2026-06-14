import React from 'react';
import {Pressable, StyleSheet, Text, ViewStyle} from 'react-native';
import {colors} from '../theme/colors';

type Props = {
  label: string;
  symbol: string;
  onPress: () => void;
  disabled?: boolean;
  hitSlop?: number;
  style?: ViewStyle;
};

export function IconButton({label, symbol, onPress, disabled, hitSlop, style}: Props) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      disabled={disabled}
      hitSlop={hitSlop}
      onPress={onPress}
      style={({pressed}) => [
        styles.button,
        pressed && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}>
      <Text style={styles.symbol}>{symbol}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    backgroundColor: colors.ink,
    borderRadius: 8,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  disabled: {
    opacity: 0.4,
  },
  pressed: {
    opacity: 0.78,
  },
  symbol: {
    color: colors.paper,
    fontSize: 20,
    fontWeight: '700',
  },
});
