export type InputMode = "audio" | "text";
export type OutputMode = "audio_and_text" | "text_only";
export type Topic = { topic_id: string; title: string };

export type TopicPack = {
  topic_pack_id: string;
  topic_id: string;
  status: "pending" | "ready" | "failed";
  overview?: string;
  discussion_axes: string[];
  personal_angles?: string[];
  user_cheat_sheet: string[];
  is_dummy: boolean;
};

export type Session = { session_id: string; status: string; participants: string[] };
export type SessionStatus = { session_id: string; status: string; expires_at: string | null; review_available: boolean };

export type GrammarFeedback = {
  utterance_id?: string | null;
  original: string;
  suggestion: string;
  explanation_ja: string;
  severity: string;
};

export type Review = {
  session_id: string;
  summary: string;
  score_total: number;
  score_communication: number;
  score_language: number;
  conversation_feedback: string[];
  grammar_feedback: GrammarFeedback[];
  user_utterance_count: number;
  ai_utterance_count: number;
  question_count: number;
  duration_seconds: number | null;
};

// speakerId is the persona name chosen for this session (e.g. "alice", "emma"),
// plus the two fixed roles "user" and "system". Any persona name from
// PersonaId.PERSONA_POOL on the backend can appear here.
export type SpeakerId = string;
export type ConversationMessage = {
  id: string;
  speakerId: SpeakerId;
  text: string;
  status?: "streaming" | "final" | "error";
};

export type StreamEvent = {
  type: string;
  speakerId?: string;
  text?: string;
  message?: string;
  remainingSeconds?: number;
};

export type StreamConnection = {
  sendText: (text: string) => void;
  startSpeech: () => void;
  sendAudio: (audio: ArrayBuffer) => void;
  endSpeech: () => void;
  interrupt: () => void;
  close: () => void;
};
