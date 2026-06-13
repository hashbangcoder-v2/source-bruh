import React from 'react';
import {StyleSheet, Text} from 'react-native';
import {colors} from '../theme/colors';

type Props = {
  message?: string;
  tone?: 'good' | 'bad' | 'neutral';
};

export function StatusText({message, tone = 'neutral'}: Props) {
  if (!message) {
    return null;
  }
  return <Text style={[styles.text, styles[tone]]}>{message}</Text>;
}

const styles = StyleSheet.create({
  text: {
    fontSize: 13,
    lineHeight: 18,
    marginTop: 10,
  },
  good: {
    color: colors.green,
  },
  bad: {
    color: colors.red,
  },
  neutral: {
    color: colors.muted,
  },
});
