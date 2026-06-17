import {NativeModules} from 'react-native';

type ImageClipboardModule = {
  copyImageUrlToClipboard: (url: string) => Promise<boolean>;
};

const ImageClipboard = NativeModules.ImageClipboard as ImageClipboardModule | undefined;

export async function copyImageToClipboard(url: string) {
  if (!ImageClipboard?.copyImageUrlToClipboard) {
    throw new Error('Image clipboard is not available on this device.');
  }
  return ImageClipboard.copyImageUrlToClipboard(url);
}
