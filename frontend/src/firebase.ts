import { initializeApp } from "firebase/app";
import { ReCaptchaEnterpriseProvider, getToken, initializeAppCheck } from "firebase/app-check";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID as string,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string,
};

const recaptchaSiteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;

// Only wired up when the app is actually talking to a real backend (mock mode
// has no App Check-enforcing API to satisfy, and local dev may not have a
// site key configured at all).
const appCheck =
  recaptchaSiteKey && firebaseConfig.appId
    ? initializeAppCheck(initializeApp(firebaseConfig), {
        provider: new ReCaptchaEnterpriseProvider(recaptchaSiteKey),
        isTokenAutoRefreshEnabled: true,
      })
    : null;

export async function getAppCheckToken(): Promise<string | null> {
  if (!appCheck) return null;
  const result = await getToken(appCheck, /* forceRefresh= */ false);
  return result.token;
}
