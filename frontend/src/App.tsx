import { FormEvent, useEffect, useRef, useState } from "react";
import { api, usingMockApi } from "./api";
import type { ConversationMessage, InputMode, OutputMode, Review, Session, StreamConnection, StreamEvent, Topic, TopicPack } from "./types";

type Screen = "auth" | "setup" | "conversation" | "review";
const newMessage = (speakerId: ConversationMessage["speakerId"], text: string, status: ConversationMessage["status"] = "final"): ConversationMessage => ({ id: crypto.randomUUID(), speakerId, text, status });

export default function App() {
  const [screen, setScreen] = useState<Screen>("auth");
  const [token, setToken] = useState<string | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicPack, setTopicPack] = useState<TopicPack | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function login(username: string, password: string) {
    setError(null);
    try {
      const auth = await api.login(username, password);
      setToken(auth.access_token);
      setTopics(await api.topics(auth.access_token));
      setScreen("setup");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "認証に失敗しました。");
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
      if (pack.status !== "ready") throw new Error("Topic Packの生成に失敗しました。");
      const created = await api.createSession(pack.topic_pack_id, agentCount, language, inputMode, outputMode, token);
      setTopicPack(pack);
      setSession(created);
      setScreen("conversation");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "セッションを開始できませんでした。");
    }
  }

  async function finishSession() {
    if (!token || !session) return;
    setError(null);
    try {
      setReview(await api.endSession(session.session_id, token));
      setScreen("review");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Reviewを生成できませんでした。");
    }
  }

  function reset() {
    setTopicPack(null);
    setSession(null);
    setReview(null);
    setError(null);
    setScreen("setup");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">REAL CONVERSATION</p>
          <h1>Conversation Stage</h1>
        </div>
        <span className={`environment ${usingMockApi ? "mock" : "live"}`}>{usingMockApi ? "Mock API" : "Live API"}</span>
      </header>
      {error && <div className="notice error" role="alert">{error}</div>}
      {screen === "auth" && <AuthScreen onSubmit={login} />}
      {screen === "setup" && <SetupScreen topics={topics} onStart={startSession} />}
      {screen === "conversation" && session && token && <ConversationScreen session={session} token={token} topicPack={topicPack} onFinish={finishSession} onError={setError} />}
      {screen === "review" && review && <ReviewScreen review={review} onNewSession={reset} />}
    </main>
  );
}

function AuthScreen({ onSubmit }: { onSubmit: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    await onSubmit(username, password);
    setBusy(false);
  }
  return <section className="auth-layout">
    <div className="intro">
      <p className="section-label">Group English practice</p>
      <h2>Join a conversation,<br />not a lesson.</h2>
      <p>Two AI participants keep the conversation moving. Speak when you are ready, then review how you joined in.</p>
    </div>
    <form className="form-panel" onSubmit={submit}>
      <label>Username<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} /></label>
      <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <button type="submit" disabled={busy}>{busy ? "Signing in..." : "Start"}</button>
      {usingMockApi && <p className="subtle">Mock mode accepts any non-empty credentials.</p>}
    </form>
  </section>;
}

function SetupScreen({ topics, onStart }: { topics: Topic[]; onStart: (topic: string, count: number, language: string, input: InputMode, output: OutputMode) => Promise<void> }) {
  const [topic, setTopic] = useState(topics[0]?.topic_id ?? "");
  const [agentCount, setAgentCount] = useState(2);
  const [language, setLanguage] = useState("en");
  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [outputMode, setOutputMode] = useState<OutputMode>("text_only");
  const [busy, setBusy] = useState(false);
  async function start() {
    setBusy(true);
    await onStart(topic, agentCount, language, inputMode, outputMode);
    setBusy(false);
  }
  return <section className="setup">
    <div className="section-heading"><p className="section-label">Set the stage</p><h2>Choose a topic and enter the room.</h2></div>
    <fieldset><legend>Topic</legend><div className="topic-list">{topics.map((item) => <label className={`topic-option ${topic === item.topic_id ? "selected" : ""}`} key={item.topic_id}><input type="radio" name="topic" value={item.topic_id} checked={topic === item.topic_id} onChange={() => setTopic(item.topic_id)} />{item.title}</label>)}</div></fieldset>
    <div className="settings-grid">
      <label>AI participants<select value={agentCount} onChange={(event) => setAgentCount(Number(event.target.value))}><option value={1}>1 participant</option><option value={2}>2 participants</option></select></label>
      <label>Conversation language<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="ja">Japanese</option></select></label>
      <label>Input<select value={inputMode} onChange={(event) => setInputMode(event.target.value as InputMode)}><option value="text">Text</option><option value="audio">Microphone</option></select></label>
      <label>Output<select value={outputMode} onChange={(event) => setOutputMode(event.target.value as OutputMode)}><option value="text_only">Text</option><option value="audio_and_text">Audio and text</option></select></label>
    </div>
    <button className="primary-action" type="button" onClick={start} disabled={!topic || busy}>{busy ? "Preparing topic..." : "Enter conversation"}</button>
  </section>;
}

function ConversationScreen({ session, token, topicPack, onFinish, onError }: { session: Session; token: string; topicPack: TopicPack | null; onFinish: () => Promise<void>; onError: (message: string | null) => void }) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [state, setState] = useState("Connecting...");
  const [ending, setEnding] = useState(false);
  const connection = useRef<StreamConnection | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => {
    let active = true;
    api.connect(session.session_id, token, (event) => active && handleEvent(event), (message) => onError(message)).then((stream) => { if (active) connection.current = stream; else stream.close(); }).catch((reason: unknown) => onError(reason instanceof Error ? reason.message : "会話に接続できませんでした。"));
    return () => { active = false; connection.current?.close(); };
  }, [session.session_id, token]);

  function handleEvent(event: StreamEvent) {
    if (event.type === "session.ready") { setState("Your turn"); setMessages((current) => current.length ? current : [newMessage("system", "The conversation is ready. Say hello when you are ready.")]); return; }
    if (event.type === "speaker.changed") { setState(`${capitalize(event.speaker_id ?? "Agent")} is speaking`); return; }
    if (event.type === "floor.opened" || event.type === "turn.complete") { setState("Your turn"); return; }
    if (event.type === "agent.interrupted") { setState("Interrupted. Your turn"); return; }
    if (event.type === "system.error") { onError(event.message ?? "会話を継続できませんでした。"); return; }
    if (event.type === "agent.text.delta" || event.type === "agent.text.final") {
      const speakerId = event.speaker_id === "bob" ? "bob" : "alice";
      const text = event.text ?? "";
      setMessages((current) => {
        const latest = current.at(-1);
        if (latest?.speakerId === speakerId && latest.status === "streaming") return [...current.slice(0, -1), { ...latest, text, status: event.type === "agent.text.final" ? "final" : "streaming" }];
        return [...current, newMessage(speakerId, text, event.type === "agent.text.final" ? "final" : "streaming")];
      });
    }
  }

  function sendText(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !connection.current) return;
    setMessages((current) => [...current, newMessage("user", text)]);
    setDraft("");
    setState("Thinking...");
    connection.current.sendText(text);
  }

  async function toggleMicrophone() {
    if (recorder.current?.state === "recording") { recorder.current.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      chunks.current = [];
      mediaRecorder.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      mediaRecorder.onstop = () => {
        connection.current?.sendAudio(new Blob(chunks.current, { type: mediaRecorder.mimeType }));
        connection.current?.endSpeech();
        stream.getTracks().forEach((track) => track.stop());
        setState("Thinking...");
      };
      recorder.current = mediaRecorder;
      connection.current?.interrupt();
      connection.current?.startSpeech();
      mediaRecorder.start();
      setState("Recording... click again to send");
    } catch {
      onError("マイクを利用できませんでした。ブラウザの権限を確認してください。");
    }
  }

  async function finish() { setEnding(true); await onFinish(); setEnding(false); }
  return <section className="conversation">
    <div className="conversation-head"><div><p className="section-label">Live session</p><h2>{topicPack?.overview ?? "Conversation"}</h2></div><div className="session-state">{state}</div><button className="quiet-button" type="button" onClick={() => connection.current?.interrupt()}>Interrupt</button><button className="end-button" type="button" onClick={finish} disabled={ending}>{ending ? "Ending..." : "End session"}</button></div>
    <div className="message-list" aria-live="polite">{messages.map((message) => <article className={`message ${message.speakerId}`} key={message.id}><span>{message.speakerId === "user" ? "You" : message.speakerId === "system" ? "Stage" : capitalize(message.speakerId)}</span><p>{message.text}</p></article>)}</div>
    {topicPack && <details className="hints"><summary>Conversation prompts</summary><ul>{topicPack.user_cheat_sheet.map((hint) => <li key={hint}>{hint}</li>)}</ul></details>}
    <form className="message-composer" onSubmit={sendText}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Write what you want to say" aria-label="Message" /><button type="button" className="mic-button" onClick={toggleMicrophone} title="Record audio">Mic</button><button type="submit">Send</button></form>
  </section>;
}

function ReviewScreen({ review, onNewSession }: { review: Review; onNewSession: () => void }) {
  return <section className="review"><p className="section-label">Session review</p><div className="score"><strong>{review.score_total}</strong><span>/ 100</span></div><h2>{review.summary}</h2><div className="feedback-list">{review.grammar_feedback.length ? review.grammar_feedback.map((item, index) => <article className="feedback" key={`${item.original}-${index}`}><p className="before">{item.original}</p><p className="after">{item.suggestion}</p><p>{item.explanation_ja}</p></article>) : <p className="subtle">今回は文法フィードバックはありません。</p>}</div><button type="button" onClick={onNewSession}>Start another session</button></section>;
}

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));
const capitalize = (value: string) => value.slice(0, 1).toUpperCase() + value.slice(1);
