// Mirrors api/src/services/personas.py's PERSONA_POOL. The backend randomly
// selects `agent_count` of these per session; the frontend needs the same
// catalog so it can render a consistent color/label for whichever persona
// name comes back in session.participants / speakerId, without the backend
// having to send display metadata over the wire.

export type PersonaMeta = { name: string; label: string; personality: string; personalityJa: string; color: string };

export const PERSONA_POOL: PersonaMeta[] = [
  { name: "alice", label: "Alice", personality: "warm and curious, always asks a follow-up", personalityJa: "温かく好奇心旺盛。いつも一言質問を返す", color: "var(--color-persona-alice)" },
  { name: "bob", label: "Bob", personality: "thoughtful, offers gentle counterpoints", personalityJa: "思慮深く、やんわり反対意見も出す", color: "var(--color-persona-bob)" },
  { name: "emma", label: "Emma", personality: "energetic, loves sharing personal stories", personalityJa: "エネルギッシュで、自分の体験談を話すのが好き", color: "var(--color-persona-emma)" },
  { name: "david", label: "David", personality: "calm and analytical, concise and rarely interrupts", personalityJa: "冷静で分析的。簡潔で、あまり口を挟まない", color: "var(--color-persona-david)" },
  { name: "mia", label: "Mia", personality: "playful and witty, keeps the mood relaxed", personalityJa: "遊び心があってウィットに富み、場を和ませる", color: "var(--color-persona-mia)" },
];

const BY_NAME = new Map(PERSONA_POOL.map((persona) => [persona.name, persona]));

export function personaFor(name: string): PersonaMeta {
  return BY_NAME.get(name) ?? { name, label: name.slice(0, 1).toUpperCase() + name.slice(1), personality: "", personalityJa: "", color: "var(--color-muted)" };
}
