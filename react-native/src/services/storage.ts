import AsyncStorage from '@react-native-async-storage/async-storage';
import {serverUrls} from '../config';

const SERVER_MODE_KEY = 'sourceBruh.serverMode';
const LOCAL_URL_KEY = 'sourceBruh.localServerUrl';

export type ServerMode = 'local' | 'production';

export async function getServerMode(): Promise<ServerMode> {
  const value = await AsyncStorage.getItem(SERVER_MODE_KEY);
  return value === 'production' ? 'production' : 'local';
}

export async function setServerMode(mode: ServerMode) {
  await AsyncStorage.setItem(SERVER_MODE_KEY, mode);
}

export async function getLocalServerUrl() {
  return (await AsyncStorage.getItem(LOCAL_URL_KEY)) || serverUrls.localDefault;
}

export async function setLocalServerUrl(url: string) {
  await AsyncStorage.setItem(LOCAL_URL_KEY, url.trim());
}

export async function getServerBaseUrl() {
  const mode = await getServerMode();
  return mode === 'local' ? getLocalServerUrl() : serverUrls.production;
}
