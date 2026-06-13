import {AppState, NativeModules} from 'react-native';
import {getIdToken} from './auth';
import {getServerBaseUrl} from './storage';
import {
  addImageFromUrl,
  commitImagePreview,
  resolveImageFromUrl,
} from './api';

export type SharedImage = {
  contentUri?: string;
  fileName?: string;
  mimeType?: string;
  text?: string;
  webUrl?: string;
};

export type PreparedSharedImage = SharedImage & {
  previewId?: string;
  previewUri: string;
  resolvedImageUrl?: string | null;
  sourceKind: 'file' | 'url';
};

const URL_PATTERN = /https?:\/\/[^\s"'<>]+/i;

function firstUrl(value?: string | null) {
  return value?.match(URL_PATTERN)?.[0];
}

function normalizeSharedItem(item: any): SharedImage | null {
  const webUrl = item?.weblink || firstUrl(item?.text);
  const contentUri = item?.contentUri || item?.filePath;
  if (!contentUri && !webUrl) {
    return null;
  }
  return {
    contentUri,
    fileName: item?.fileName,
    mimeType: item?.mimeType,
    text: item?.text,
    webUrl,
  };
}

function shouldIgnoreShareError(error: unknown) {
  const message = String(error || '');
  return (
    message.includes('Intent.getAction()') ||
    message.includes('null object reference') ||
    message.includes('Invalid file type') ||
    message.includes('No Activity found')
  );
}

async function readSharedFiles() {
  const module = NativeModules.ReceiveSharingIntent;
  if (!module?.getFileNames) {
    return [];
  }
  const fileObject = await module.getFileNames();
  if (!fileObject || typeof fileObject !== 'object') {
    return [];
  }
  return Object.keys(fileObject).map(key => fileObject[key]);
}

export function listenForSharedImages(
  onImage: (image: SharedImage) => void,
  onError: (message: string) => void,
) {
  let active = true;

  const checkForShare = () => {
    readSharedFiles()
      .then((files: any[]) => {
        if (!active) {
          return;
        }
        const firstImage = files.map(normalizeSharedItem).find(Boolean);
        if (firstImage) {
          onImage(firstImage);
        }
      })
      .catch((error: unknown) => {
        if (active && error && !shouldIgnoreShareError(error)) {
          onError(String(error));
        }
      });
  };

  checkForShare();
  const subscription = AppState.addEventListener('change', state => {
    if (state === 'active') {
      checkForShare();
    }
  });

  return () => {
    active = false;
    subscription.remove();
  };
}

export async function prepareSharedImage(image: SharedImage): Promise<PreparedSharedImage> {
  if (!image.contentUri && image.webUrl) {
    console.info(`[share] POST /images/resolve-url ${image.webUrl}`);
    const preview = await resolveImageFromUrl({
      imageUrl: image.webUrl,
      pageUrl: image.webUrl,
      albumPath: 'android-share',
      albumTitle: image.fileName || 'Android share',
    });
    const serverBaseUrl = await getServerBaseUrl();
    return {
      ...image,
      previewId: preview.preview_id,
      previewUri: `${serverBaseUrl}${preview.preview_url}`,
      resolvedImageUrl: preview.resolved_image_url,
      mimeType: preview.mime_type || image.mimeType,
      sourceKind: 'url',
    };
  }

  if (!image.contentUri) {
    throw new Error('Shared item did not include an image file or URL.');
  }

  return {
    ...image,
    previewUri: image.contentUri,
    sourceKind: 'file',
  };
}

export async function uploadSharedImage(
  image: SharedImage | PreparedSharedImage,
  userDescription = '',
) {
  if ('previewId' in image && image.previewId) {
    console.info(`[share] POST /images/commit-preview ${image.previewId}`);
    return commitImagePreview({
      previewId: image.previewId,
      userDescription,
    });
  }

  if (!image.contentUri && image.webUrl) {
    console.info(`[share] POST /images/from-url ${image.webUrl}`);
    return addImageFromUrl({
      imageUrl: image.webUrl,
      pageUrl: image.webUrl,
      albumPath: 'android-share',
      albumTitle: image.fileName || 'Android share',
      userDescription,
    });
  }

  if (!image.contentUri) {
    throw new Error('Shared item did not include an image file or URL.');
  }

  const token = await getIdToken();
  const serverBaseUrl = await getServerBaseUrl();
  const form = new FormData();
  form.append('file', {
    uri: image.contentUri,
    name: image.fileName || 'shared-image.jpg',
    type: image.mimeType || 'image/jpeg',
  } as any);
  form.append('page_url', image.webUrl || image.text || '');
  form.append('album_title', image.fileName || 'Android share');
  form.append('album_path', 'android-share');
  form.append('user_description', userDescription);

  console.info(
    `[share] POST ${serverBaseUrl}/images/upload ${image.mimeType || 'image/jpeg'}`,
  );
  const response = await fetch(`${serverBaseUrl}/images/upload`, {
    method: 'POST',
    headers: token ? {Authorization: `Bearer ${token}`} : undefined,
    body: form,
  });

  const text = await response.text();
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = JSON.parse(text)?.detail || detail;
    } catch {
      detail = text || detail;
    }
    throw new Error(`Upload failed: ${response.status} ${detail}`);
  }

  return text ? JSON.parse(text) : {ok: true};
}
