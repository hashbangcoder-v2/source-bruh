import { auth, googleProvider } from "./firebase";
import { signInWithPopup } from "firebase/auth";

// Listen for messages from the extension popup
chrome.runtime.onMessage.addListener(async (message) => {
  if (message.type === 'firebase-login') {
    try {
      const result = await signInWithPopup(auth, googleProvider);
      // Send success message back to the popup
      chrome.runtime.sendMessage({ type: 'firebase-login-success', payload: result.user });
    } catch (error) {
      // Send error message back to the popup
      chrome.runtime.sendMessage({ type: 'firebase-login-failure', payload: error.message });
    }
  }
  return true; // Indicates an async response
});
