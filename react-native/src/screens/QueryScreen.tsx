import React, {useState} from 'react';
import {
  ActivityIndicator,
  FlatList,
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {IconButton} from '../components/IconButton';
import {BackIconButton} from '../components/BackIconButton';
import {StatusText} from '../components/StatusText';
import {SearchResult, getImageUrl, searchImages} from '../services/api';
import {copyImageToClipboard} from '../services/imageClipboard';
import {colors} from '../theme/colors';

type Props = {
  onSettings: () => void;
  onProfile: () => void;
  shareStatus?: string;
  shareError?: string;
};

type TileProps = {
  item: SearchResult;
  onPress: () => void;
};

function ResultTile({item, onPress}: TileProps) {
  const [uri, setUri] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  React.useEffect(() => {
    let mounted = true;
    let settled = false;
    const path = item.thumb_url || item.image_url || `/image/${item.image_rowid}`;
    setUri(null);
    setFailed(false);
    const timeout = setTimeout(() => {
      if (mounted && !settled) {
        setFailed(true);
      }
    }, 5000);

    getImageUrl(path)
      .then(value => {
        settled = true;
        if (mounted) {
          setUri(value);
        }
      })
      .catch(() => {
        settled = true;
        if (mounted) {
          setFailed(true);
        }
      })
      .finally(() => clearTimeout(timeout));

    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [item.image_rowid, item.image_url, item.thumb_url]);

  return (
    <Pressable onPress={onPress} style={styles.tile}>
      {uri && !failed ? (
        <Image source={{uri}} style={styles.image} onError={() => setFailed(true)} />
      ) : (
        <View style={styles.placeholder}>
          {failed ? (
            <Text style={styles.placeholderText}>No image</Text>
          ) : (
            <ActivityIndicator color={colors.muted} />
          )}
        </View>
      )}
    </Pressable>
  );
}

function ProfileIconButton({onPress}: {onPress: () => void}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Profile"
      hitSlop={10}
      onPress={onPress}
      style={({pressed}) => [styles.profileButton, pressed && styles.pressedButton]}>
      <View style={styles.profileIconHead} />
      <View style={styles.profileIconBody} />
    </Pressable>
  );
}

function SearchIconButton({
  disabled,
  onPress,
}: {
  label?: string;
  symbol?: string;
  disabled?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Search"
      disabled={disabled}
      onPress={onPress}
      style={({pressed}) => [
        styles.searchButton,
        pressed && styles.pressedButton,
        disabled && styles.disabledButton,
      ]}>
      <View style={styles.searchIconCircle} />
      <View style={styles.searchIconHandle} />
    </Pressable>
  );
}

function ordinal(day: number) {
  if (day > 10 && day < 20) {
    return `${day}th`;
  }
  const suffix = day % 10 === 1 ? 'st' : day % 10 === 2 ? 'nd' : day % 10 === 3 ? 'rd' : 'th';
  return `${day}${suffix}`;
}

function formatDisplayDate(value?: string | null) {
  if (!value) {
    return '';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const month = parsed.toLocaleString('en-US', {month: 'short'});
  return `${ordinal(parsed.getDate())} ${month} ${parsed.getFullYear()}`;
}

function getSourceLabel(item: SearchResult) {
  return item.source_url || item.album_title || item.image_rowid;
}

export function QueryScreen({onSettings, onProfile, shareStatus, shareError}: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [pageSize, setPageSize] = useState(30);

  const runSearch = async (nextPageSize = pageSize) => {
    const trimmed = query.trim();
    if (!trimmed || loading) {
      return;
    }
    setLoading(true);
    setError('');
    try {
      const found = await searchImages(trimmed, nextPageSize);
      setResults(found);
      setPageSize(nextPageSize);
      if (!found.length) {
        setError('No relevant images found for that query.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed.');
    } finally {
      setLoading(false);
    }
  };

  const loadMore = () => {
    if (results.length >= pageSize && !loading) {
      runSearch(pageSize + 30);
    }
  };

  return (
    <View style={styles.container}>
      {selectedIndex === null ? (
        <>
          <ProfileIconButton onPress={onProfile} />
          <IconButton
            label="Settings"
            symbol="⚙"
            onPress={onSettings}
            hitSlop={10}
            style={styles.settingsButton}
          />
        </>
      ) : null}

      <View
        style={[
          styles.searchShell,
          results.length ? styles.searchShellWithResults : styles.searchShellHome,
        ]}>
        {!results.length ? <Text style={styles.title}>Need a source?</Text> : null}

        <View style={styles.searchRow}>
          <TextInput
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={() => runSearch()}
            placeholder="growth OECD post-2020"
            placeholderTextColor={colors.muted}
            style={styles.input}
            autoCapitalize="none"
            returnKeyType="search"
          />
          <SearchIconButton
            label="Search"
            symbol="⌕"
            disabled={!query.trim() || loading}
            onPress={() => runSearch()}
          />
        </View>

        <StatusText message={shareStatus} tone="good" />
        <StatusText message={shareError} tone="bad" />
        <StatusText message={error} tone={results.length ? 'neutral' : 'bad'} />
      </View>

      {loading && !results.length ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.ink} />
        </View>
      ) : results.length ? (
        <FlatList
          data={results}
          keyExtractor={item => item.image_rowid}
          numColumns={3}
          contentContainerStyle={styles.grid}
          renderItem={({item, index}) => (
            <ResultTile item={item} onPress={() => setSelectedIndex(index)} />
          )}
          onEndReached={loadMore}
          onEndReachedThreshold={0.8}
          ListFooterComponent={
            loading && results.length ? (
              <ActivityIndicator color={colors.ink} style={styles.footer} />
            ) : null
          }
        />
      ) : null}

      <ResultDetailLayer
        index={selectedIndex}
        results={results}
        onClose={() => setSelectedIndex(null)}
        onSelectIndex={setSelectedIndex}
      />
    </View>
  );
}

function ResultDetailLayer({
  index,
  results,
  onClose,
  onSelectIndex,
}: {
  index: number | null;
  results: SearchResult[];
  onClose: () => void;
  onSelectIndex: (index: number) => void;
}) {
  const item = index === null ? null : results[index] || null;
  const [uri, setUri] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState('');
  const [failed, setFailed] = useState(false);
  const canGoPrevious = index !== null && index > 0;
  const canGoNext = index !== null && index < results.length - 1;

  const goPrevious = React.useCallback(() => {
    if (canGoPrevious && index !== null) {
      onSelectIndex(index - 1);
    }
  }, [canGoPrevious, index, onSelectIndex]);

  const goNext = React.useCallback(() => {
    if (canGoNext && index !== null) {
      onSelectIndex(index + 1);
    }
  }, [canGoNext, index, onSelectIndex]);

  const panResponder = React.useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => false,
        onMoveShouldSetPanResponderCapture: (_, gestureState) =>
          Math.abs(gestureState.dx) > 12 &&
          Math.abs(gestureState.dx) > Math.abs(gestureState.dy) * 1.25,
        onMoveShouldSetPanResponder: (_, gestureState) =>
          Math.abs(gestureState.dx) > 12 &&
          Math.abs(gestureState.dx) > Math.abs(gestureState.dy) * 1.25,
        onPanResponderRelease: (_, gestureState) => {
          if (gestureState.dx < -36) {
            goNext();
          } else if (gestureState.dx > 36) {
            goPrevious();
          }
        },
      }),
    [goNext, goPrevious],
  );

  React.useEffect(() => {
    let mounted = true;
    setUri(null);
    setFailed(false);
    setCopyStatus('');
    if (!item) {
      return () => {
        mounted = false;
      };
    }
    getImageUrl(item.image_url || `/image/${item.image_rowid}`)
      .then(value => {
        if (mounted) {
          setUri(value);
        }
      })
      .catch(() => {
        if (mounted) {
          setFailed(true);
        }
      });
    return () => {
      mounted = false;
    };
  }, [item]);

  const handleCopy = async () => {
    if (!uri) {
      return;
    }
    setCopyStatus('Copying image...');
    try {
      await copyImageToClipboard(uri);
      setCopyStatus('Image copied.');
    } catch (err) {
      setCopyStatus(err instanceof Error ? err.message : 'Copy failed.');
    }
  };

  const note = item?.user_description || item?.description || '';
  const displayDate = formatDisplayDate(item?.timestamp);
  const sourceLabel = item ? getSourceLabel(item) : '';

  if (!item) {
    return null;
  }

  return (
      <View style={styles.detailScreen} {...panResponder.panHandlers}>
        <View style={styles.detailHeader}>
          <BackIconButton onPress={onClose} light />
          <Text style={styles.resultCounter}>
            {index !== null ? `${index + 1} / ${results.length}` : ''}
          </Text>
          <Pressable
            disabled={!uri}
            onPress={handleCopy}
            style={[styles.headerButton, !uri && styles.headerButtonDisabled]}>
            <Text style={styles.headerButtonText}>Copy</Text>
          </Pressable>
        </View>

        <View style={styles.detailImageShell}>
          {uri && !failed ? (
            <Image
              source={{uri}}
              resizeMode="contain"
              style={styles.detailImage}
              onError={() => setFailed(true)}
            />
          ) : (
            <View style={styles.detailPlaceholder}>
              {failed ? (
                <Text style={styles.placeholderText}>No image</Text>
              ) : (
                <ActivityIndicator color={colors.paper} />
              )}
            </View>
          )}
        </View>

        <View style={styles.metadataPanel}>
          {note ? (
            <Text style={styles.descriptionPrimary}>{note}</Text>
          ) : (
            <Text style={styles.descriptionMuted}>No description saved.</Text>
          )}
          {displayDate ? <Text style={styles.meta}>{displayDate}</Text> : null}
          {sourceLabel ? <Text style={styles.sourcePath}>{sourceLabel}</Text> : null}
          {copyStatus ? <Text style={styles.copyStatus}>{copyStatus}</Text> : null}
        </View>
      </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.paper,
    flex: 1,
    paddingHorizontal: 20,
  },
  settingsButton: {
    elevation: 4,
    position: 'absolute',
    right: 18,
    top: 56,
    zIndex: 10,
  },
  profileButton: {
    alignItems: 'center',
    backgroundColor: colors.ink,
    borderRadius: 8,
    elevation: 4,
    height: 44,
    justifyContent: 'center',
    position: 'absolute',
    right: 72,
    top: 56,
    width: 44,
    zIndex: 10,
  },
  profileIconHead: {
    backgroundColor: colors.paper,
    borderRadius: 5,
    height: 10,
    marginBottom: 3,
    width: 10,
  },
  profileIconBody: {
    backgroundColor: colors.paper,
    borderTopLeftRadius: 10,
    borderTopRightRadius: 10,
    height: 10,
    width: 22,
  },
  searchButton: {
    alignItems: 'center',
    backgroundColor: colors.ink,
    borderRadius: 8,
    height: 44,
    justifyContent: 'center',
    position: 'relative',
    width: 44,
  },
  searchIconCircle: {
    borderColor: colors.paper,
    borderRadius: 8,
    borderWidth: 2.4,
    height: 17,
    marginLeft: -3,
    marginTop: -3,
    width: 17,
  },
  searchIconHandle: {
    backgroundColor: colors.paper,
    borderRadius: 2,
    height: 11,
    position: 'absolute',
    right: 13,
    top: 27,
    transform: [{rotate: '-45deg'}],
    width: 2.4,
  },
  pressedButton: {
    opacity: 0.78,
  },
  disabledButton: {
    opacity: 0.4,
  },
  searchShell: {
    alignItems: 'center',
    gap: 16,
    paddingHorizontal: 8,
  },
  searchShellHome: {
    flex: 1,
    justifyContent: 'center',
    paddingBottom: 86,
    paddingTop: 92,
  },
  searchShellWithResults: {
    paddingBottom: 12,
    paddingTop: 92,
  },
  title: {
    color: colors.ink,
    fontSize: 30,
    fontWeight: '800',
    textAlign: 'center',
  },
  searchRow: {
    alignSelf: 'center',
    flexDirection: 'row',
    gap: 10,
    maxWidth: 560,
    width: '100%',
  },
  input: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.ink,
    flex: 1,
    fontSize: 16,
    minHeight: 44,
    paddingHorizontal: 12,
  },
  loading: {
    flex: 1,
    justifyContent: 'center',
  },
  grid: {
    gap: 8,
    paddingBottom: 36,
    paddingTop: 16,
  },
  tile: {
    aspectRatio: 1,
    backgroundColor: colors.chip,
    borderRadius: 8,
    flex: 1 / 3,
    margin: 4,
    overflow: 'hidden',
  },
  image: {
    height: '100%',
    width: '100%',
  },
  placeholder: {
    alignItems: 'center',
    backgroundColor: colors.chip,
    flex: 1,
    justifyContent: 'center',
  },
  placeholderText: {
    color: colors.muted,
    fontSize: 12,
  },
  footer: {
    padding: 20,
  },
  detailScreen: {
    backgroundColor: colors.ink,
    bottom: 0,
    elevation: 40,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
    zIndex: 1000,
  },
  detailHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 52,
    zIndex: 2,
  },
  headerButton: {
    alignItems: 'center',
    backgroundColor: 'rgba(251,250,246,0.16)',
    borderColor: 'rgba(251,250,246,0.22)',
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 40,
    minWidth: 72,
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  headerButtonDisabled: {
    opacity: 0.45,
  },
  headerButtonText: {
    color: colors.paper,
    fontSize: 14,
    fontWeight: '800',
  },
  resultCounter: {
    color: colors.paper,
    fontSize: 13,
    fontWeight: '700',
    opacity: 0.72,
  },
  detailImageShell: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 8,
    paddingVertical: 12,
  },
  detailImage: {
    height: '100%',
    width: '100%',
  },
  detailPlaceholder: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  metadataPanel: {
    backgroundColor: colors.paper,
    borderTopLeftRadius: 8,
    borderTopRightRadius: 8,
    gap: 8,
    paddingBottom: 28,
    paddingHorizontal: 18,
    paddingTop: 16,
  },
  descriptionPrimary: {
    color: colors.ink,
    fontSize: 16,
    fontWeight: '700',
    lineHeight: 22,
  },
  descriptionMuted: {
    color: colors.muted,
    fontSize: 16,
    lineHeight: 20,
  },
  meta: {
    color: colors.ink,
    fontSize: 13,
    fontWeight: '600',
  },
  sourcePath: {
    color: colors.muted,
    fontSize: 11,
    lineHeight: 15,
  },
  copyStatus: {
    color: colors.green,
    fontSize: 13,
    fontWeight: '700',
  },
});
