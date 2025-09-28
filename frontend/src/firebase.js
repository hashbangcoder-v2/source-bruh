// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyACzuIKQway0ImS_Jq_XmT8PrxfT06id78",
  authDomain: "source-bruh.firebaseapp.com",
  projectId: "source-bruh",
  storageBucket: "source-bruh.firebasestorage.app",
  messagingSenderId: "700625261564",
  appId: "1:700625261564:web:4f8e2b75f6f372ddc5d879",
  measurementId: "G-RMN4PG1T6P"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
