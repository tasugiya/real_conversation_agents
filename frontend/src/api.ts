import type { InputMode, OutputMode, Review, Session, StreamConnection, StreamEvent, Topic, TopicPack } from "./types";

const configuredMock = import.meta.env.VITE_USE_MOCK_API;
const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "");
export const usingMockApi = configuredMock !== "false" || !baseUrl;
type AuthResult = { access_token: string; expires_at: string };
type TopicPackJob = { job_id: string; topic_pack_id: string; status: string };
const fixedTopics: Topic[] = [{ topic_id: "campus_life", title: "Campus life" }, { topic_id: "weekend_plans", title: "Weekend plans" }, { topic_id: "favorite_media", title: "Favorite movies or shows" }];
const mockPacks = new Map<string, TopicPack>();
const mockSessions = new Map<string, { session: Session; userTexts: string[] }>();
const id = (prefix: string) => `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`;

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init?.headers ?? {}) } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  async login(username: string, password: string): Promise<AuthResult> {
    if (usingMockApi) {
      if (!username || !password) throw new Error("ユーザー名とパスワードを入力してください。");
      return { access_token: "mock-access-token", expires_at: new Date(Date.now() + 3_600_000).toISOString() };
    }
    return request<AuthResult>("/v1/auth", null, { method: "POST", body: JSON.stringify({ username, password }) });
  },
  async topics(token: string): Promise<Topic[]> {
    return usingMockApi ? fixedTopics : (await request<{ topics: Topic[] }>("/v1/topics", token)).topics;
  },
  async createTopicPack(topicId: string, token: string): Promise<TopicPackJob> {
    if (usingMockApi) {
      const topicPackId = id("pack");
      mockPacks.set(topicPackId, { topic_pack_id: topicPackId, topic_id: topicId, status: "pending", discussion_axes: [], user_cheat_sheet: [], is_dummy: true });
      window.setTimeout(() => {
        const topic = fixedTopics.find((item) => item.topic_id === topicId)?.title ?? topicId;
        mockPacks.set(topicPackId, { topic_pack_id: topicPackId, topic_id: topicId, status: "ready", overview: `A short group conversation about ${topic.toLowerCase()}.`, discussion_axes: ["Share a personal experience", "Ask a follow-up question"], user_cheat_sheet: ["I think...", "That reminds me of...", "What about you?"], is_dummy: true });
      }, 650);
      return { job_id: topicPackId, topic_pack_id: topicPackId, status: "pending" };
    }
    return request<TopicPackJob>("/v1/topic-packs", token, { method: "POST", body: JSON.stringify({ topic_id: topicId }), headers: { "Idempotency-Key": crypto.randomUUID() } });
  },
  async topicPack(topicPackId: string, token: string): Promise<TopicPack> {
    if (usingMockApi) {
      const pack = mockPacks.get(topicPackId);
      if (!pack) throw new Error("Topic Packが見つかりません。");
      return pack;
    }
    return request<TopicPack>(`/v1/topic-packs/${topicPackId}`, token);
  },
  async createSession(topicPackId: string, agentCount: number, language: string, inputMode: InputMode, outputMode: OutputMode, token: string): Promise<Session> {
    if (usingMockApi) {
      const session: Session = { session_id: id("session"), status: "created", participants: ["alice", "bob"].slice(0, agentCount) };
      mockSessions.set(session.session_id, { session, userTexts: [] });
      return session;
    }
    return request<Session>("/v1/sessions", token, { method: "POST", body: JSON.stringify({ topic_pack_id: topicPackId, agent_count: agentCount, language, input_mode: inputMode, output_mode: outputMode }) });
  },
  async endSession(sessionId: string, token: string): Promise<Review> {
    if (usingMockApi) {
      const userTexts = mockSessions.get(sessionId)?.userTexts ?? [];
      return { session_id: sessionId, summary: userTexts.length ? "You joined a short group conversation and shared your own point of view." : "This session ended before a user response was recorded.", score_total: userTexts.length ? 78 : 0, grammar_feedback: userTexts.length ? [{ original: userTexts[0], suggestion: userTexts[0], explanation_ja: "会話を始められています。次は相手への質問を一つ加えてみましょう。", severity: "low" }] : [] };
    }
    return request<Review>(`/v1/sessions/${sessionId}/end`, token, { method: "POST" });
  },
  async connect(sessionId: string, token: string, onEvent: (event: StreamEvent) => void, onError: (message: string) => void): Promise<StreamConnection> {
    if (usingMockApi) return connectMock(sessionId, onEvent);
    // WebSocket handshakes can't carry an Authorization header, so the long-lived
    // access token is exchanged here for a short-lived, single-use stream ticket
    // that travels safely in the URL query string instead.
    const ticket = await request<{ stream_ticket: string }>(`/v1/sessions/${sessionId}/stream-ticket`, token, { method: "POST" });
    const socket = new WebSocket(`${baseUrl!.replace(/^http/, "ws")}/v1/sessions/${sessionId}/stream?ticket=${encodeURIComponent(ticket.stream_ticket)}`);
    socket.onmessage = (message) => {
      if (typeof message.data === "string") {
        const data = JSON.parse(message.data) as { type: string; speaker_id?: string; payload?: { text?: string; message?: string } };
        onEvent({ type: data.type, speaker_id: data.speaker_id, text: data.payload?.text, message: data.payload?.message });
      }
    };
    socket.onerror = () => onError("会話ストリームへの接続に失敗しました。");
    return { sendText: (text) => socket.send(JSON.stringify({ type: "user.text", payload: { text } })), startSpeech: () => socket.send(JSON.stringify({ type: "user.speech.start" })), sendAudio: (audio) => socket.send(audio), endSpeech: () => socket.send(JSON.stringify({ type: "user.speech.end" })), interrupt: () => socket.send(JSON.stringify({ type: "user.interrupt" })), close: () => socket.close() };
  },
};

function connectMock(sessionId: string, onEvent: (event: StreamEvent) => void): StreamConnection {
  let closed = false;
  window.setTimeout(() => onEvent({ type: "session.ready" }), 100);
  return {
    sendText: (text) => {
      mockSessions.get(sessionId)?.userTexts.push(text);
      const response = text.includes("?") ? "That is a thoughtful question. I would probably choose something simple and enjoyable." : "That sounds interesting. What made you feel that way?";
      window.setTimeout(() => !closed && onEvent({ type: "speaker.changed", speaker_id: "alice" }), 250);
      window.setTimeout(() => !closed && onEvent({ type: "agent.text.delta", speaker_id: "alice", text: response }), 500);
      window.setTimeout(() => !closed && onEvent({ type: "agent.text.final", speaker_id: "alice", text: response }), 900);
      window.setTimeout(() => !closed && onEvent({ type: "turn.complete", speaker_id: "alice" }), 950);
      window.setTimeout(() => !closed && onEvent({ type: "floor.opened" }), 1000);
    },
    startSpeech: () => undefined, sendAudio: () => undefined, endSpeech: () => undefined,
    interrupt: () => onEvent({ type: "agent.interrupted" }), close: () => { closed = true; },
  };
}
