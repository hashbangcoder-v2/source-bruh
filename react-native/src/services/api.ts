import {getIdToken} from './auth';
import {getServerBaseUrl} from './storage';

export type SearchResult = {
  image_rowid: string;
  distance: number;
  description?: string | null;
  user_description?: string | null;
  album_title?: string | null;
  timestamp?: string | null;
  thumb_url: string;
  image_url: string;
  source_url?: string | null;
};

export type SettingsResponse = {
  email: string;
  name: string;
  album_url: string;
  gemini_key_set: boolean;
};

export type ProfileResponse = {
  email: string;
  name: string;
  photo_url: string;
  stats: {
    files_indexed: number;
    queries_last_week: number;
    queries_lifetime: number;
  };
};

export type CropRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ResolvedImagePreview = {
  ok: boolean;
  preview_id: string;
  preview_url: string;
  resolved_image_url?: string | null;
  mime_type?: string | null;
};

export async function makeAuthenticatedRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getIdToken();
  const serverBaseUrl = await getServerBaseUrl();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${serverBaseUrl}${path}`, {
    ...options,
    headers,
  });
  console.info(`[api] ${options.method || 'GET'} ${serverBaseUrl}${path} -> ${response.status}`);

  const text = await response.text();
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = JSON.parse(text)?.detail || detail;
    } catch {
      detail = text || detail;
    }
    const error = new Error(`Request failed: ${response.status} ${detail}`);
    (error as Error & {status?: number}).status = response.status;
    throw error;
  }

  if (!text) {
    return null as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

export async function getSettings() {
  return makeAuthenticatedRequest<SettingsResponse>('/settings');
}

export async function getProfile() {
  return makeAuthenticatedRequest<ProfileResponse>('/profile');
}

export async function saveAlbumUrl(albumUrl: string) {
  return makeAuthenticatedRequest<{ok: boolean; album_url: string}>(
    '/settings/album-url',
    {
      method: 'POST',
      body: JSON.stringify({album_url: albumUrl}),
    },
  );
}

export async function saveGeminiKey(apiKey: string) {
  return makeAuthenticatedRequest<{ok: boolean}>('/settings/gemini-key', {
    method: 'POST',
    body: JSON.stringify({api_key: apiKey}),
  });
}

export async function addImageFromUrl(params: {
  imageUrl: string;
  pageUrl?: string;
  albumPath?: string;
  albumTitle?: string;
  userDescription?: string;
}) {
  return makeAuthenticatedRequest<{ok: boolean; media_id: string}>(
    '/images/from-url',
    {
      method: 'POST',
      body: JSON.stringify({
        image_url: params.imageUrl,
        page_url: params.pageUrl || params.imageUrl,
        album_path: params.albumPath || 'android-share',
        album_title: params.albumTitle || 'Android share',
        user_description: params.userDescription || '',
      }),
    },
  );
}

export async function resolveImageFromUrl(params: {
  imageUrl: string;
  pageUrl?: string;
  albumPath?: string;
  albumTitle?: string;
}) {
  return makeAuthenticatedRequest<ResolvedImagePreview>('/images/resolve-url', {
    method: 'POST',
    body: JSON.stringify({
      image_url: params.imageUrl,
      page_url: params.pageUrl || params.imageUrl,
      album_path: params.albumPath || 'android-share',
      album_title: params.albumTitle || 'Android share',
    }),
  });
}

export async function commitImagePreview(params: {
  previewId: string;
  userDescription?: string;
  cropRect?: CropRect | null;
}) {
  return makeAuthenticatedRequest<{ok: boolean; media_id: string}>(
    '/images/commit-preview',
    {
      method: 'POST',
      body: JSON.stringify({
        preview_id: params.previewId,
        user_description: params.userDescription || '',
        crop_x: params.cropRect?.x,
        crop_y: params.cropRect?.y,
        crop_width: params.cropRect?.width,
        crop_height: params.cropRect?.height,
      }),
    },
  );
}

export async function searchImages(query: string, topK = 30) {
  return makeAuthenticatedRequest<SearchResult[]>(
    `/search?q=${encodeURIComponent(query)}&top_k=${topK}`,
  );
}

export async function testHealth() {
  const serverBaseUrl = await getServerBaseUrl();
  const response = await fetch(`${serverBaseUrl}/health`);
  console.info(`[api] GET ${serverBaseUrl}/health -> ${response.status}`);
  return response.ok;
}

export async function getImageUrl(path: string) {
  const serverBaseUrl = await getServerBaseUrl();
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${serverBaseUrl}${path}`;
}
