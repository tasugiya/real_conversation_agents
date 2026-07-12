// Client-only persistence. Nothing here is a security boundary -- it exists
// purely to survive a reload/tab-close without losing the user's place.
// sessionStorage (cleared when the tab closes) holds the auth token and the
// in-progress session pointer; localStorage (survives across tabs/days)
// holds the small list of past session ids used by the /reviews screen.

const AUTH_KEY = "rc.auth";
const ACTIVE_SESSION_KEY = "rc.active_session";
const RECENT_SESSIONS_KEY = "rc.recent_sessions";
const LOCALE_KEY = "rc.locale";
const MAX_RECENT_SESSIONS = 20;

export type StoredAuth = { token: string; expiresAt: string };
export type StoredActiveSession = { sessionId: string; topicPackId: string; participants: string[] };

function readJson<T>(storage: Storage, key: string): T | null {
  try {
    const raw = storage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export const authStorage = {
  get(): StoredAuth | null {
    const auth = readJson<StoredAuth>(sessionStorage, AUTH_KEY);
    if (!auth || new Date(auth.expiresAt) <= new Date()) return null;
    return auth;
  },
  set(auth: StoredAuth): void {
    sessionStorage.setItem(AUTH_KEY, JSON.stringify(auth));
  },
  clear(): void {
    sessionStorage.removeItem(AUTH_KEY);
  },
};

export const activeSessionStorage = {
  get(): StoredActiveSession | null {
    return readJson<StoredActiveSession>(sessionStorage, ACTIVE_SESSION_KEY);
  },
  set(session: StoredActiveSession): void {
    sessionStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(session));
  },
  clear(): void {
    sessionStorage.removeItem(ACTIVE_SESSION_KEY);
  },
};

export const localeStorage = {
  get(): string | null {
    return localStorage.getItem(LOCALE_KEY);
  },
  set(locale: string): void {
    localStorage.setItem(LOCALE_KEY, locale);
  },
};

export const recentSessionsStorage = {
  list(): string[] {
    return readJson<string[]>(localStorage, RECENT_SESSIONS_KEY) ?? [];
  },
  add(sessionId: string): void {
    const current = recentSessionsStorage.list().filter((id) => id !== sessionId);
    localStorage.setItem(RECENT_SESSIONS_KEY, JSON.stringify([sessionId, ...current].slice(0, MAX_RECENT_SESSIONS)));
  },
};
