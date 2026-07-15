import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, api, usingMockApi } from "./api";
import { LocaleContext, readStoredLocale, translate, useLocale, useT, type Locale } from "./i18n";
import { PERSONA_POOL, personaFor } from "./personas";
import { navigate, useRoute, type Route } from "./router";
import { activeSessionStorage, authStorage, localeStorage, recentSessionsStorage } from "./storage";
import type { ConversationMessage, InputMode, OutputMode, Review, Session, SessionStatus, StreamConnection, StreamEvent, Topic, TopicPack } from "./types";

const FLOW_STEPS: { key: Route; labelKey: "stepper.setup" | "stepper.conversation" | "stepper.review" }[] = [
  { key: "/setup", labelKey: "stepper.setup" },
  { key: "/session", labelKey: "stepper.conversation" },
  { key: "/review", labelKey: "stepper.review" },
];

const inputClass = "min-h-[44px] w-full rounded-md border border-border bg-white px-3.5 text-ink outline-none transition focus:border-accent";
const primaryButtonClass = "min-h-[44px] rounded-md bg-accent px-5 font-semibold text-white transition hover:bg-accent-dark disabled:cursor-wait disabled:opacity-60";

const newMessage = (speakerId: string, text: string, status: ConversationMessage["status"] = "final"): ConversationMessage => ({ id: crypto.randomUUID(), speakerId, text, status });

export default function App() {
  const [locale, setLocaleState] = useState<Locale>(() => readStoredLocale());
  function setLocale(next: Locale) {
    localeStorage.set(next);
    setLocaleState(next);
  }
  const t = (key: Parameters<typeof translate>[1], vars?: Record<string, string | number>) => translate(locale, key, vars);
  return (
    <LocaleContext.Provider value={{ locale, setLocale, t }}>
      <AppShell />
    </LocaleContext.Provider>
  );
}

function AppShell() {
  const route = useRoute();
  const t = useT();
  const [locale, setLocale] = useLocale();
  const [token, setToken] = useState<string | null>(() => authStorage.get()?.token ?? null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [topicPack, setTopicPack] = useState<TopicPack | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [congested, setCongested] = useState(false);
  const [booting, setBooting] = useState(true);

  // Runs once, only to rehydrate state after a reload -- normal in-app
  // navigation (login -> setup -> session -> review) already sets this
  // state directly and never needs this path.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      let auth = authStorage.get();
      const startPath = window.location.pathname;

      if (!auth) {
        // prod skips password verification server-side (routes/auth.py), so
        // a silent attempt here lets those users skip AuthScreen entirely.
        // Environments that do require a real password 401 immediately and
        // fall through to showing it, same as before.
        try {
          const attempt = await api.login("", "");
          auth = { token: attempt.access_token, expiresAt: attempt.expires_at };
          authStorage.set(auth);
        } catch {
          authStorage.clear();
          if (startPath !== "/") navigate("/", { replace: true });
          setBooting(false);
          return;
        }
      }

      setToken(auth.token);
      if (startPath === "/") navigate("/setup", { replace: true });
      // Trend topics are no longer auto-fetched here (see loadTopics) --
      // SetupScreen's "load trends" button triggers it explicitly, since
      // every automatic fetch on login/reload was hitting the X API and
      // its cost regardless of whether the user actually starts a session.

      if (startPath === "/session" || startPath === "/review") {
        const active = activeSessionStorage.get();
        if (!active) {
          navigate("/setup", { replace: true });
        } else {
          try {
            const status = await api.getSession(active.sessionId, auth.token);
            if (cancelled) return;
            const stillReviewable = status.review_available && (!status.expires_at || new Date(status.expires_at) > new Date());
            if (status.status === "completed") {
              if (!stillReviewable) {
                setError(t("app.error.sessionExpired"));
                activeSessionStorage.clear();
                navigate("/setup", { replace: true });
              } else {
                const restoredReview = await api.review(active.sessionId, auth.token);
                if (cancelled) return;
                setReview(restoredReview);
                setSession({ session_id: active.sessionId, status: "completed", participants: active.participants });
                if (startPath !== "/review") navigate("/review", { replace: true });
              }
            } else {
              const pack = await api.topicPack(active.topicPackId, auth.token);
              if (cancelled) return;
              setTopicPack(pack);
              setSession({ session_id: active.sessionId, status: status.status, participants: active.participants });
              if (startPath !== "/session") navigate("/session", { replace: true });
            }
          } catch (reason) {
            if (!cancelled) {
              setError(reason instanceof Error ? reason.message : t("app.error.sessionRestoreFailed"));
              activeSessionStorage.clear();
              navigate("/setup", { replace: true });
            }
          }
        }
      }

      if (!cancelled) setBooting(false);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadTopics(authToken: string, region: string) {
    setTopicsLoading(true);
    api
      .topics(authToken, region)
      .then((fetched) => setTopics(fetched))
      .catch((reason) => setError(reason instanceof Error ? reason.message : t("app.error.topicsFailed")))
      .finally(() => setTopicsLoading(false));
  }

  async function login(username: string, password: string) {
    setError(null);
    try {
      const auth = await api.login(username, password);
      authStorage.set({ token: auth.access_token, expiresAt: auth.expires_at });
      setToken(auth.access_token);
      navigate("/setup");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("app.error.loginFailed"));
    }
  }

  async function startSession(selectedTopic: string, agentCount: number, language: string, inputMode: InputMode, outputMode: OutputMode) {
    if (!token) return;
    setError(null);
    try {
      const job = await api.createTopicPack(selectedTopic, token);
      let pack = await api.topicPack(job.topic_pack_id, token);
      for (let attempt = 0; pack.status === "pending" && attempt < 20; attempt += 1) {
        await delay(500);
        pack = await api.topicPack(job.topic_pack_id, token);
      }
      if (pack.status !== "ready") throw new Error(t("app.error.topicPackFailed"));
      const created = await api.createSession(pack.topic_pack_id, agentCount, language, inputMode, outputMode, token);
      activeSessionStorage.set({ sessionId: created.session_id, topicPackId: pack.topic_pack_id, participants: created.participants });
      setTopicPack(pack);
      setSession(created);
      navigate("/session");
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 503) {
        setCongested(true);
        return;
      }
      setError(reason instanceof Error ? reason.message : t("app.error.sessionStartFailed"));
    }
  }

  async function finishSession() {
    if (!token || !session) return;
    setError(null);
    try {
      const result = await api.endSession(session.session_id, token);
      recentSessionsStorage.add(session.session_id);
      setReview(result);
      navigate("/review");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("app.error.reviewFailed"));
    }
  }

  function reset() {
    setTopicPack(null);
    setSession(null);
    setReview(null);
    setError(null);
    activeSessionStorage.clear();
    navigate("/setup");
  }

  function goToRecentSessions() {
    if (route === "/session" && !window.confirm(t("app.confirmLeaveSession"))) return;
    navigate("/reviews");
  }

  if (booting) {
    return <main className="grid min-h-[60vh] place-items-center text-sm text-muted">{t("app.loading")}</main>;
  }

  return (
    <main className="mx-auto w-[min(100%-2rem,1040px)] pb-14 pt-8">
      <header className="mb-9 flex items-baseline justify-between border-b border-border pb-5">
        <div>
          <p className="mb-1.5 text-[0.7rem] font-extrabold uppercase tracking-[0.14em] text-accent">Real Conversation</p>
          <h1 className="font-display text-lg font-semibold">Conversation Stage</h1>
        </div>
        <div className="flex items-center gap-5">
          {(route === "/setup" || route === "/session" || route === "/review") && <Stepper current={route} />}
          {token && route !== "/reviews" && (
            <button type="button" onClick={goToRecentSessions} className="text-xs font-semibold text-muted transition hover:text-accent">
              {t("app.recentSessions")}
            </button>
          )}
          <PillGroup ariaLabel="Display language" value={locale} onChange={setLocale} options={[{ value: "ja", label: "日本語" }, { value: "en", label: "EN" }]} />
        </div>
      </header>

      {error && (
        <div role="alert" className="mb-6 border-l-4 border-danger bg-danger-soft px-4 py-3 text-danger">
          {error}
        </div>
      )}

      {route === "/" && <AuthScreen onSubmit={login} />}
      {route === "/setup" && (congested
        ? <CongestionScreen onRetry={() => setCongested(false)} />
        : <SetupScreen topics={topics} topicsLoading={topicsLoading} onLoadTopics={(region) => token && loadTopics(token, region)} onStart={startSession} />)}
      {route === "/session" && session && token && (
        <ConversationScreen session={session} token={token} topicPack={topicPack} onFinish={finishSession} onError={setError} onReset={reset} />
      )}
      {route === "/review" && review && session && <ReviewScreen review={review} participants={session.participants} onNewSession={reset} onGoHome={goToRecentSessions} />}
      {route === "/reviews" && token && <RecentSessionsScreen token={token} onNewConversation={reset} />}

      {import.meta.env.DEV && (
        <span
          title={usingMockApi ? "Mock API" : "Live API"}
          className={`fixed bottom-3 right-3 h-2.5 w-2.5 rounded-full ${usingMockApi ? "bg-amber-400" : "bg-emerald-400"}`}
        />
      )}
    </main>
  );
}

function Stepper({ current }: { current: Route }) {
  const t = useT();
  const activeIndex = FLOW_STEPS.findIndex((step) => step.key === current);
  return (
    <ol className="flex items-center gap-2 text-xs font-semibold">
      {FLOW_STEPS.map((step, index) => (
        <li key={step.key} className="flex items-center gap-2">
          {index > 0 && <span aria-hidden className="h-px w-6 bg-border" />}
          <span className={index === activeIndex ? "text-accent" : index < activeIndex ? "text-ink" : "text-muted"}>{t(step.labelKey)}</span>
        </li>
      ))}
    </ol>
  );
}

function PillGroup<T extends string | number>({ options, value, onChange, ariaLabel }: { options: { value: T; label: string }[]; value: T; onChange: (value: T) => void; ariaLabel: string }) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={String(option.value)}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={`min-h-[38px] rounded-full border px-4 text-sm font-semibold transition ${selected ? "border-accent bg-accent text-white" : "border-border bg-white text-ink hover:border-accent/60"}`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function AuthScreen({ onSubmit }: { onSubmit: (username: string, password: string) => Promise<void> }) {
  const t = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    await onSubmit(username, password);
    setBusy(false);
  }
  return (
    <section className="grid min-h-[56vh] items-center gap-12 md:grid-cols-[1.15fr_0.85fr] md:gap-24">
      <div className="max-w-lg">
        <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.1em] text-accent">{t("auth.eyebrow")}</p>
        <h2 className="font-display text-4xl font-medium leading-[1.1] sm:text-5xl">
          {t("auth.headline1")}
          <br />
          {t("auth.headline2")}
        </h2>
        <p className="mt-5 max-w-md leading-relaxed text-muted">{t("auth.subhead")}</p>
      </div>
      <form onSubmit={submit} className="grid gap-4 border-t border-border pt-6 md:border-l md:border-t-0 md:pl-9 md:pt-0">
        <label className="grid gap-1.5 text-sm font-semibold">
          {t("auth.username")}
          <input className={inputClass} autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label className="grid gap-1.5 text-sm font-semibold">
          {t("auth.password")}
          <input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button type="submit" className={primaryButtonClass} disabled={busy}>
          {busy ? t("auth.submitBusy") : t("auth.submit")}
        </button>
        {usingMockApi && <p className="text-xs text-muted">{t("auth.mockHint")}</p>}
      </form>
    </section>
  );
}

function SetupScreen({ topics, topicsLoading, onLoadTopics, onStart }: { topics: Topic[]; topicsLoading: boolean; onLoadTopics: (region: string) => void; onStart: (topic: string, count: number, language: string, input: InputMode, output: OutputMode) => Promise<void> }) {
  const t = useT();
  const [locale] = useLocale();
  const [topic, setTopic] = useState(topics[0]?.topic_id ?? "");
  const [region, setRegion] = useState("japan");
  const [agentCount, setAgentCount] = useState(2);
  const [language, setLanguage] = useState("en");
  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [outputMode, setOutputMode] = useState<OutputMode>("text_only");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!topic && topics[0]) setTopic(topics[0].topic_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topics]);
  async function start() {
    setBusy(true);
    await onStart(topic, agentCount, language, inputMode, outputMode);
    setBusy(false);
  }
  return (
    <section className="max-w-3xl">
      <div className="mb-8">
        <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.1em] text-accent">{t("setup.eyebrow")}</p>
        <h2 className="font-display text-3xl font-medium">{t("setup.title")}</h2>
      </div>

      <fieldset className="mb-8 border-0 p-0">
        <legend className="mb-2.5 text-sm font-bold">{t("setup.topicLegend")}</legend>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <PillGroup
            ariaLabel={t("setup.region")}
            value={region}
            onChange={setRegion}
            options={[
              { value: "japan", label: t("setup.regionJapan") },
              { value: "tokyo", label: t("setup.regionTokyo") },
              { value: "worldwide", label: t("setup.regionWorldwide") },
            ]}
          />
          <button
            type="button"
            onClick={() => onLoadTopics(region)}
            disabled={topicsLoading}
            className="min-h-[38px] rounded-full border border-accent px-4 text-sm font-semibold text-accent transition hover:bg-accent-soft disabled:opacity-60"
          >
            {topicsLoading ? t("setup.topicLoading") : topics.length ? t("setup.reloadTopics") : t("setup.loadTopics")}
          </button>
        </div>
        {topicsLoading && topics.length === 0 ? (
          <div className="flex items-center gap-3 rounded-lg border border-dashed border-border bg-white/60 px-4 py-6 text-sm text-muted">
            <span aria-hidden className="h-2 w-2 shrink-0 animate-ping rounded-full bg-accent" />
            {t("setup.topicLoading")}
          </div>
        ) : topics.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border bg-white/60 px-4 py-6 text-sm text-muted">
            {t("setup.topicEmpty")}
          </div>
        ) : (
          <div className="grid gap-2.5 sm:grid-cols-3">
            {topics.map((item) => {
              const selected = topic === item.topic_id;
              return (
                <label
                  key={item.topic_id}
                  className={`relative block cursor-pointer rounded-lg border bg-white p-4 text-sm font-semibold transition ${selected ? "border-accent shadow-[inset_0_-3px_0_var(--color-accent)]" : "border-border hover:border-accent/50"}`}
                >
                  <input type="radio" name="topic" className="absolute h-px w-px opacity-0" value={item.topic_id} checked={selected} onChange={() => setTopic(item.topic_id)} />
                  {item.title}
                </label>
              );
            })}
          </div>
        )}
      </fieldset>

      <div className="mb-8">
        <p className="mb-2.5 text-sm font-bold">{t("setup.personaHeading")}</p>
        <p className="mb-3 text-xs text-muted">{t("setup.personaSub", { count: agentCount })}</p>
        <ul className="flex flex-wrap gap-2.5">
          {PERSONA_POOL.map((persona) => (
            <li key={persona.name} className="flex items-center gap-2 rounded-full border border-border bg-white py-1.5 pl-1.5 pr-3.5">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold text-white" style={{ backgroundColor: persona.color }}>
                {persona.label.slice(0, 1)}
              </span>
              <span>
                <span className="block text-sm font-semibold leading-none">{persona.label}</span>
                <span className="block max-w-[13rem] text-xs leading-tight text-muted">{locale === "ja" ? persona.personalityJa : persona.personality}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mb-9 grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-sm font-bold">{t("setup.aiVoices")}</p>
          <PillGroup ariaLabel={t("setup.aiVoices")} value={agentCount} onChange={setAgentCount} options={[{ value: 1, label: "1" }, { value: 2, label: "2" }, { value: 3, label: "3" }]} />
        </div>
        <div>
          <p className="mb-2 text-sm font-bold">{t("setup.language")}</p>
          <PillGroup ariaLabel={t("setup.language")} value={language} onChange={setLanguage} options={[{ value: "en", label: t("setup.languageEnglish") }, { value: "ja", label: t("setup.languageJapanese") }]} />
        </div>
        <div>
          <p className="mb-2 text-sm font-bold">{t("setup.input")}</p>
          <PillGroup ariaLabel={t("setup.input")} value={inputMode} onChange={setInputMode} options={[{ value: "text", label: t("setup.inputText") }, { value: "audio", label: t("setup.inputMic") }]} />
        </div>
        <div>
          <p className="mb-2 text-sm font-bold">{t("setup.output")}</p>
          <PillGroup ariaLabel={t("setup.output")} value={outputMode} onChange={setOutputMode} options={[{ value: "text_only", label: t("setup.outputTextOnly") }, { value: "audio_and_text", label: t("setup.outputAudioText") }]} />
        </div>
      </div>

      <button type="button" className={primaryButtonClass} onClick={start} disabled={!topic || busy}>
        {busy ? t("setup.preparing") : t("setup.enter")}
      </button>
    </section>
  );
}

function StageChip({ label, color, active, isUser }: { label: string; color?: string; active: boolean; isUser?: boolean }) {
  const chipColor = isUser ? "var(--color-accent)" : color;
  return (
    <div className="flex flex-col items-center gap-1.5">
      <span className="relative grid h-12 w-12 place-items-center">
        {active && <span aria-hidden className="absolute inset-0 animate-ping rounded-full opacity-40" style={{ backgroundColor: chipColor }} />}
        <span className="relative grid h-12 w-12 place-items-center rounded-full text-sm font-bold text-white" style={{ backgroundColor: chipColor }}>
          {label.slice(0, 1)}
        </span>
      </span>
      <span className="text-xs font-semibold text-muted">{label}</span>
    </div>
  );
}

function MicIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <rect x="9" y="2" width="6" height="11" rx="3" />
      <path d="M5 10a7 7 0 0 0 14 0" />
      <line x1="12" y1="17" x2="12" y2="21" />
      <line x1="8" y1="21" x2="16" y2="21" />
    </svg>
  );
}

function InterruptedScreen({ onRetry, onEvaluate, onGoHome, evaluating }: { onRetry: () => void; onEvaluate: () => void; onGoHome: () => void; evaluating: boolean }) {
  const t = useT();
  return (
    <section className="grid min-h-[50vh] place-items-center text-center">
      <div className="max-w-sm">
        <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.1em] text-danger">{t("interrupted.eyebrow")}</p>
        <h2 className="font-display mb-3 text-2xl font-medium">{t("interrupted.title")}</h2>
        <p className="mb-8 text-sm text-muted">{t("interrupted.body")}</p>
        <div className="grid gap-2.5">
          <button type="button" onClick={onRetry} className={primaryButtonClass}>
            {t("interrupted.retry")}
          </button>
          <button type="button" onClick={onEvaluate} disabled={evaluating} className="min-h-[44px] rounded-md border border-accent px-5 font-semibold text-accent transition hover:bg-accent-soft disabled:opacity-60">
            {evaluating ? t("interrupted.evaluateBusy") : t("interrupted.evaluate")}
          </button>
          <button type="button" onClick={onGoHome} className="min-h-[44px] rounded-md border border-border px-5 font-semibold text-muted transition hover:border-accent/50 hover:text-ink">
            {t("interrupted.goHome")}
          </button>
        </div>
      </div>
    </section>
  );
}

function CongestionScreen({ onRetry }: { onRetry: () => void }) {
  const t = useT();
  return (
    <section className="grid min-h-[50vh] place-items-center text-center">
      <div className="max-w-sm">
        <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.1em] text-danger">{t("congestion.eyebrow")}</p>
        <h2 className="font-display mb-3 text-2xl font-medium">{t("congestion.title")}</h2>
        <p className="mb-8 text-sm text-muted">{t("congestion.body")}</p>
        <button type="button" onClick={onRetry} className={primaryButtonClass}>
          {t("congestion.retry")}
        </button>
      </div>
    </section>
  );
}

const MAX_STREAM_RETRIES = 3;

function ConversationScreen({ session, token, topicPack, onFinish, onError, onReset }: { session: Session; token: string; topicPack: TopicPack | null; onFinish: () => Promise<void>; onError: (message: string | null) => void; onReset: () => void }) {
  const t = useT();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [activeSpeaker, setActiveSpeaker] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [recording, setRecording] = useState(false);
  const [timeWarning, setTimeWarning] = useState<number | null>(null);
  const [ending, setEnding] = useState(false);
  const [connectionState, setConnectionState] = useState<"connecting" | "live" | "interrupted">("connecting");
  const connection = useRef<StreamConnection | null>(null);
  const micContext = useRef<AudioContext | null>(null);
  const micStream = useRef<MediaStream | null>(null);
  const micNode = useRef<AudioWorkletNode | null>(null);
  const activeRef = useRef(true);
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef<number | undefined>(undefined);
  // Set once the server ends the session on purpose (time limit reached).
  // Guards handleStreamProblem so the WS close that follows isn't mistaken
  // for a dropped connection and retried -- see BUG-020.
  const sessionEndedRef = useRef(false);

  function handleEvent(event: StreamEvent) {
    switch (event.type) {
      case "session.ready":
        setMessages((current) => (current.length ? current : [newMessage("system", t("conversation.readySystemMessage"))]));
        return;
      case "agent.text.delta":
      case "agent.text.final": {
        const speakerId = event.speakerId ?? session.participants[0] ?? "agent";
        const text = event.text ?? "";
        const isFinal = event.type === "agent.text.final";
        setActiveSpeaker(speakerId);
        setThinking(false);
        setMessages((current) => {
          const latest = current.at(-1);
          if (latest?.speakerId === speakerId && latest.status === "streaming") return [...current.slice(0, -1), { ...latest, text, status: isFinal ? "final" : "streaming" }];
          return [...current, newMessage(speakerId, text, isFinal ? "final" : "streaming")];
        });
        return;
      }
      case "user.transcript.final":
        if (event.text) setMessages((current) => [...current, newMessage("user", event.text!)]);
        return;
      case "turn.complete":
        setActiveSpeaker(null);
        setThinking(false);
        return;
      case "floor.opened":
        setThinking(false);
        return;
      case "agent.interrupted":
        setActiveSpeaker(null);
        setThinking(false);
        return;
      case "session.time_warning":
        setTimeWarning(event.remainingSeconds ?? null);
        return;
      case "session.wrap":
      case "session.time_limit":
        // The server is about to close the WS on purpose -- either the
        // conversation reached its natural end (session.wrap: the agent
        // said goodbye and called its wrap-up tool) or the hard time limit
        // hit. Wrap up the same way the manual "end" button does instead
        // of waiting for onclose to (wrongly) treat this as a dropped
        // connection -- see BUG-020.
        if (!sessionEndedRef.current) {
          sessionEndedRef.current = true;
          void finish();
        }
        return;
      case "system.error":
        // The server always closes the connection right after sending this
        // (rate limit exceeded, or an unhandled exception in the stream) --
        // wrap up the same way session.time_limit does instead of letting
        // the resulting onclose retry into a dead end.
        onError(event.message ?? t("conversation.errorContinue"));
        if (!sessionEndedRef.current) {
          sessionEndedRef.current = true;
          void finish();
        }
        return;
      default:
        return;
    }
  }

  async function attemptConnect() {
    setConnectionState("connecting");
    try {
      const stream = await api.connect(session.session_id, token, (event) => activeRef.current && handleEvent(event), (message) => activeRef.current && handleStreamProblem(message));
      if (!activeRef.current) {
        stream.close();
        return;
      }
      connection.current = stream;
      retryCountRef.current = 0;
      setConnectionState("live");
    } catch (reason) {
      if (activeRef.current) handleStreamProblem(reason instanceof Error ? reason.message : t("conversation.errorConnect"));
    }
  }

  function handleStreamProblem(_message: string) {
    if (!activeRef.current) return;
    if (sessionEndedRef.current) return;
    retryCountRef.current += 1;
    if (retryCountRef.current > MAX_STREAM_RETRIES) {
      setConnectionState("interrupted");
      return;
    }
    retryTimerRef.current = window.setTimeout(() => activeRef.current && attemptConnect(), 1500);
  }

  function manualRetry() {
    retryCountRef.current = 0;
    attemptConnect();
  }

  useEffect(() => {
    activeRef.current = true;
    attemptConnect();
    return () => {
      activeRef.current = false;
      window.clearTimeout(retryTimerRef.current);
      connection.current?.close();
      micNode.current?.disconnect();
      micContext.current?.close();
      micStream.current?.getTracks().forEach((track) => track.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.session_id, token]);

  useEffect(() => {
    if (connectionState !== "live") return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [connectionState]);

  function sendText(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !connection.current) return;
    setMessages((current) => [...current, newMessage("user", text)]);
    setDraft("");
    setThinking(true);
    connection.current.sendText(text);
  }

  function stopMicrophone() {
    micNode.current?.port.close();
    micNode.current?.disconnect();
    micNode.current = null;
    void micContext.current?.close();
    micContext.current = null;
    micStream.current?.getTracks().forEach((track) => track.stop());
    micStream.current = null;
    connection.current?.endSpeech();
    setThinking(true);
    setRecording(false);
  }

  async function toggleMicrophone() {
    if (recording) {
      stopMicrophone();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Match the backend's expected wire format (audio/pcm;rate=16000,
      // see agent_engine_client.py) by creating the AudioContext at 16kHz
      // directly -- the browser resamples the mic's native rate into it.
      const audioContext = new AudioContext({ sampleRate: 16000 });
      await audioContext.audioWorklet.addModule(new URL("./pcm-worklet.js", import.meta.url));
      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, "pcm-worklet-processor");
      workletNode.port.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          connection.current?.sendAudio(event.data);
        } else if (event.data?.type === "silence") {
          // Sustained silence after speech was detected -- auto-stop as a
          // safety net for users who forget to press the mic button again
          // (the button still works for an immediate manual stop too).
          stopMicrophone();
        }
      };
      // Deliberately not connected to audioContext.destination -- we don't
      // want to hear our own mic input played back.
      source.connect(workletNode);
      micContext.current = audioContext;
      micStream.current = stream;
      micNode.current = workletNode;
      connection.current?.interrupt();
      connection.current?.startSpeech();
      setRecording(true);
    } catch {
      onError(t("conversation.errorMic"));
    }
  }

  async function finish() {
    setEnding(true);
    await onFinish();
    setEnding(false);
  }

  if (connectionState === "interrupted") {
    return <InterruptedScreen onRetry={manualRetry} onEvaluate={finish} onGoHome={onReset} evaluating={ending} />;
  }

  const statusText = connectionState === "connecting"
    ? t("conversation.statusConnecting")
    : recording
      ? t("conversation.statusRecording")
      : thinking
        ? t("conversation.statusThinking")
        : activeSpeaker
          ? t("conversation.statusSpeaking", { name: personaFor(activeSpeaker).label })
          : t("conversation.statusYourTurn");

  return (
    <section className="flex h-[calc(100vh-15rem)] min-h-[34rem] flex-col">
      <div className="flex items-start justify-between gap-4 border-b border-border pb-4">
        <div>
          <p className="mb-1 text-xs font-extrabold uppercase tracking-[0.1em] text-accent">{t("conversation.eyebrow")}</p>
          <h2 className="font-display max-w-md text-xl font-semibold">{topicPack?.overview ?? t("conversation.fallbackTitle")}</h2>
        </div>
        <button type="button" onClick={finish} disabled={ending} className="shrink-0 rounded-full border border-danger px-4 py-1.5 text-xs font-semibold text-danger transition hover:bg-danger-soft disabled:opacity-60">
          {ending ? t("conversation.ending") : t("conversation.end")}
        </button>
      </div>

      <div className="flex flex-col items-center gap-3 border-b border-border py-5">
        <div className="flex items-center gap-6">
          <StageChip label={t("conversation.you")} active={recording || thinking} isUser />
          {session.participants.map((name) => (
            <StageChip key={name} label={personaFor(name).label} color={personaFor(name).color} active={activeSpeaker === name} />
          ))}
        </div>
        <p aria-live="polite" className="text-xs font-semibold uppercase tracking-wide text-muted">
          {statusText}
        </p>
      </div>

      {timeWarning !== null && (
        <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-center text-xs font-semibold text-amber-800">{t("conversation.timeWarning", { minutes: Math.ceil(timeWarning / 60) })}</p>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto py-5" aria-live="polite">
        {messages.map((message) => {
          if (message.speakerId === "system") {
            return (
              <p key={message.id} className="border-l-2 border-border pl-3 text-sm text-muted">
                {message.text}
              </p>
            );
          }
          const isUser = message.speakerId === "user";
          const persona = isUser ? null : personaFor(message.speakerId);
          return (
            <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${isUser ? "bg-accent text-white" : "border border-border bg-white"}`} style={!isUser ? { borderLeftWidth: 3, borderLeftColor: persona!.color } : undefined}>
                {!isUser && (
                  <p className="mb-0.5 text-xs font-bold" style={{ color: persona!.color }}>
                    {persona!.label}
                  </p>
                )}
                <p className="leading-relaxed">{message.text}</p>
              </div>
            </div>
          );
        })}
      </div>

      {topicPack && topicPack.user_cheat_sheet.length > 0 && (
        <details className="border-t border-border py-3 text-sm text-muted">
          <summary className="cursor-pointer font-semibold text-ink">{t("conversation.prompts")}</summary>
          <ul className="mt-2 space-y-1 pl-4">
            {topicPack.user_cheat_sheet.map((hint) => (
              <li key={hint} className="list-disc">
                {hint}
              </li>
            ))}
          </ul>
        </details>
      )}

      <form onSubmit={sendText} className="flex items-center gap-2 border-t border-border pt-4">
        <button type="button" onClick={() => connection.current?.interrupt()} className="shrink-0 rounded-full border border-accent px-3.5 py-2 text-xs font-semibold text-accent transition hover:bg-accent-soft">
          {t("conversation.jumpIn")}
        </button>
        <input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={t("conversation.placeholder")} aria-label="Message" className={`${inputClass} rounded-full`} />
        <button
          type="button"
          onClick={toggleMicrophone}
          aria-pressed={recording}
          title="Record audio"
          className={`relative grid h-11 w-11 shrink-0 place-items-center rounded-full text-white transition ${recording ? "bg-danger" : "bg-accent hover:bg-accent-dark"}`}
        >
          {recording && <span aria-hidden className="absolute inset-0 animate-ping rounded-full bg-danger opacity-50" />}
          <MicIcon className="relative h-5 w-5" />
        </button>
        <button type="submit" className="min-h-[44px] shrink-0 rounded-full bg-accent px-5 font-semibold text-white transition hover:bg-accent-dark">
          {t("conversation.send")}
        </button>
      </form>
    </section>
  );
}

function ReviewScreen({ review, participants, onNewSession, onGoHome }: { review: Review; participants: string[]; onNewSession: () => void; onGoHome: () => void }) {
  const t = useT();
  const minutes = review.duration_seconds != null ? Math.round(review.duration_seconds / 60) : null;
  return (
    <section className="max-w-2xl">
      <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.1em] text-accent">{t("review.eyebrow")}</p>
      <div className="mb-1 flex items-baseline gap-2 text-accent">
        <strong className="font-display text-6xl font-semibold leading-none">{review.score_total}</strong>
        <span className="text-sm font-bold">/ 100</span>
      </div>
      <div className="mb-5 flex gap-5 text-sm text-muted">
        <span>
          {t("review.communication")} <strong className="text-ink">{review.score_communication}</strong>
        </span>
        <span>
          {t("review.language")} <strong className="text-ink">{review.score_language}</strong>
        </span>
      </div>
      <h2 className="font-display mb-5 max-w-xl text-lg font-medium leading-relaxed">{review.summary}</h2>

      {participants.length > 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-2 text-sm text-muted">
          <span>{t("review.talkedWith")}</span>
          {participants.map((name) => {
            const persona = personaFor(name);
            return (
              <span key={name} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-white py-1 pl-1 pr-2.5">
                <span className="grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-white" style={{ backgroundColor: persona.color }}>
                  {persona.label.slice(0, 1)}
                </span>
                {persona.label}
              </span>
            );
          })}
        </div>
      )}

      {review.conversation_feedback.length > 0 && (
        <ul className="mb-6 space-y-1.5 border-t border-border pt-4 text-sm">
          {review.conversation_feedback.map((point, index) => (
            <li key={index} className="flex gap-2">
              <span className="text-accent">•</span>
              {point}
            </li>
          ))}
        </ul>
      )}

      <div className="mb-6 border-t border-border">
        {review.grammar_feedback.length ? (
          review.grammar_feedback.map((item, index) => (
            <article key={`${item.original}-${index}`} className="border-b border-border py-4">
              <p className="mb-1.5 text-danger line-through">{item.original}</p>
              <p className="mb-1.5 font-semibold text-accent">{item.suggestion}</p>
              <p className="text-sm text-muted">{item.explanation_ja}</p>
            </article>
          ))
        ) : (
          <p className="pt-4 text-sm text-muted">{t("review.noGrammarFeedback")}</p>
        )}
      </div>

      <div className="mb-7 flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted">
        <span>{t("review.turns", { count: review.user_utterance_count })}</span>
        <span>{t("review.questions", { count: review.question_count })}</span>
        {minutes != null && <span>{t("review.duration", { minutes })}</span>}
      </div>

      <div className="flex flex-wrap gap-2.5">
        <button type="button" onClick={onNewSession} className={primaryButtonClass}>
          {t("review.newSession")}
        </button>
        <button type="button" onClick={onGoHome} className="min-h-[44px] rounded-md border border-border px-5 font-semibold text-muted transition hover:border-accent/50 hover:text-ink">
          {t("review.goHome")}
        </button>
      </div>
    </section>
  );
}

function RecentSessionsScreen({ token, onNewConversation }: { token: string; onNewConversation: () => void }) {
  const t = useT();
  const [entries, setEntries] = useState<{ id: string; status: SessionStatus | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      const ids = recentSessionsStorage.list();
      const results = await Promise.all(
        ids.map(async (sessionId) => {
          try {
            return { id: sessionId, status: await api.getSession(sessionId, token) };
          } catch {
            return { id: sessionId, status: null };
          }
        }),
      );
      if (active) {
        setEntries(results);
        setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [token]);

  async function toggle(sessionId: string) {
    if (expanded === sessionId) {
      setExpanded(null);
      return;
    }
    setExpanded(sessionId);
    if (!reviews[sessionId]) {
      try {
        const fetchedReview = await api.review(sessionId, token);
        setReviews((current) => ({ ...current, [sessionId]: fetchedReview }));
      } catch (reason) {
        setLoadError(reason instanceof Error ? reason.message : t("recentSessions.errorLoad"));
      }
    }
  }

  const viewable = entries.filter((entry) => entry.status?.review_available && (!entry.status.expires_at || new Date(entry.status.expires_at) > new Date()));

  return (
    <section className="max-w-2xl">
      <p className="mb-2 text-xs font-extrabold uppercase tracking-[0.1em] text-accent">{t("app.recentSessions")}</p>
      <h2 className="font-display mb-6 text-2xl font-medium">{t("recentSessions.title")}</h2>
      {loadError && <p className="mb-4 text-sm text-danger">{loadError}</p>}
      {!loading && viewable.length === 0 && <p className="text-sm text-muted">{t("recentSessions.empty")}</p>}
      <ul className="space-y-2.5">
        {viewable.map((entry) => (
          <li key={entry.id} className="rounded-lg border border-border bg-white">
            <button type="button" onClick={() => toggle(entry.id)} className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold">
              <span>{t("recentSessions.sessionLabel", { id: entry.id.slice(0, 8) })}</span>
              <span className="text-xs font-normal text-muted">{expanded === entry.id ? t("recentSessions.close") : t("recentSessions.open")}</span>
            </button>
            {expanded === entry.id && reviews[entry.id] && (
              <div className="border-t border-border px-4 py-3 text-sm">
                <p className="mb-1 font-bold text-accent">{reviews[entry.id].score_total} / 100</p>
                <p className="text-muted">{reviews[entry.id].summary}</p>
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-7">
        <button type="button" onClick={onNewConversation} className={primaryButtonClass}>
          {t("recentSessions.newConversation")}
        </button>
      </div>
    </section>
  );
}

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
