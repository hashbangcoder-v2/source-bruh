import React, {useState} from 'react';
import {
  ActivityIndicator,
  FlatList,
  Image,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import {IconButton} from '../components/IconButton';
import {StatusText} from '../components/StatusText';
import {SearchResult, getImageUrl, searchImages} from '../services/api';
import {colors} from '../theme/colors';

type Props = {
  onSettings: () => void;
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
    const timeout = setTimeout(() => {
      if (mounted && !uri) {
        setFailed(true);
      }
    }, 5000);

    getImageUrl(item.thumb_url)
      .then(value => {
        if (mounted) {
          setUri(value);
        }
      })
      .catch(() => setFailed(true))
      .finally(() => clearTimeout(timeout));

    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [item.thumb_url, uri]);

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

export function QueryScreen({onSettings, shareStatus, shareError}: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<SearchResult | null>(null);
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
      <IconButton
        label="Settings"
        symbol="⚙"
        onPress={onSettings}
        hitSlop={10}
        style={styles.settingsButton}
      />

      <View
        style={[
          styles.searchShell,
          results.length ? styles.searchShellWithResults : styles.searchShellHome,
        ]}>
        <Text style={styles.title}>Need a source?</Text>

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
          <IconButton
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
          renderItem={({item}) => (
            <ResultTile item={item} onPress={() => setSelected(item)} />
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

      <Modal visible={Boolean(selected)} transparent animationType="fade">
        <View style={styles.modalShade}>
          <View style={styles.modalPanel}>
            <Pressable onPress={() => setSelected(null)} style={styles.close}>
              <Text style={styles.closeText}>x</Text>
            </Pressable>
            {selected ? (
              <>
                <ResultPreview item={selected} />
                <Text style={styles.modalTitle}>
                  {selected.album_title || 'Shared image'}
                </Text>
                <Text style={styles.description}>
                  {selected.description || 'No description available.'}
                </Text>
                {selected.timestamp ? (
                  <Text style={styles.meta}>{selected.timestamp}</Text>
                ) : null}
              </>
            ) : null}
          </View>
        </View>
      </Modal>
    </View>
  );
}

function ResultPreview({item}: {item: SearchResult}) {
  const [uri, setUri] = useState<string | null>(null);
  React.useEffect(() => {
    getImageUrl(item.thumb_url).then(setUri).catch(() => setUri(null));
  }, [item.thumb_url]);
  return uri ? <Image source={{uri}} style={styles.previewImage} /> : null;
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
  modalShade: {
    alignItems: 'center',
    backgroundColor: 'rgba(21,21,18,0.68)',
    flex: 1,
    justifyContent: 'center',
    padding: 18,
  },
  modalPanel: {
    backgroundColor: colors.panel,
    borderRadius: 8,
    maxHeight: '86%',
    padding: 16,
    width: '100%',
  },
  close: {
    alignItems: 'center',
    alignSelf: 'flex-end',
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  closeText: {
    color: colors.ink,
    fontSize: 22,
    fontWeight: '800',
  },
  previewImage: {
    aspectRatio: 1,
    borderRadius: 8,
    width: '100%',
  },
  modalTitle: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: '800',
    marginTop: 14,
  },
  description: {
    color: colors.ink,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 8,
  },
  meta: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 12,
  },
});
