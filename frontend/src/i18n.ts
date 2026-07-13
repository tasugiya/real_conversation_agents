import { createContext, useContext } from "react";
import { localeStorage } from "./storage";

// Display-language toggle for the UI chrome only (buttons, headings, status
// text). It's independent of the conversation's own language setting on the
// Setup screen, and independent of content that inherently belongs to one
// language regardless of UI locale -- topic titles, cheat-sheet phrases, and
// grammar explanation_ja are English-practice material / already-localized
// backend output, not interface copy, so they never go through this dictionary.
export type Locale = "en" | "ja";

const en = {
  "app.recentSessions": "Recent sessions",
  "app.loading": "Loading…",
  "app.confirmLeaveSession": "You're in a live conversation. Leaving now will disconnect you. Continue?",
  "app.error.sessionExpired": "This session's review has expired.",
  "app.error.topicsFailed": "Couldn't load topics.",
  "app.error.sessionRestoreFailed": "Couldn't restore your session.",
  "app.error.loginFailed": "Sign-in failed.",
  "app.error.topicPackFailed": "Couldn't prepare the topic.",
  "app.error.sessionStartFailed": "Couldn't start the session.",
  "app.error.reviewFailed": "Couldn't generate your review.",

  "stepper.setup": "Set up",
  "stepper.conversation": "Conversation",
  "stepper.review": "Review",

  "auth.eyebrow": "Group English practice",
  "auth.headline1": "Join a conversation,",
  "auth.headline2": "not a lesson.",
  "auth.subhead": "A handful of AI personas keep a conversation moving on their own. Speak up whenever you are ready, then see how you did.",
  "auth.username": "Username",
  "auth.password": "Password",
  "auth.submit": "Start",
  "auth.submitBusy": "Signing in...",
  "auth.mockHint": "Mock mode accepts any non-empty credentials.",

  "setup.eyebrow": "Set the stage",
  "setup.title": "Choose a topic and enter the room.",
  "setup.topicLegend": "Topic",
  "setup.topicLoading": "Generating topics from the latest X trends…",
  "setup.loadTopics": "Load trending topics",
  "setup.reloadTopics": "Refresh trends",
  "setup.topicEmpty": "No topics loaded yet. Choose a region and load trending topics to get started.",
  "setup.region": "Trend region",
  "setup.regionJapan": "Japan",
  "setup.regionTokyo": "Tokyo",
  "setup.regionWorldwide": "Worldwide",
  "setup.personaHeading": "Who might join",
  "setup.personaSub": "{count} of these voices join at random each session.",
  "setup.aiVoices": "AI voices in the room",
  "setup.language": "Conversation language",
  "setup.input": "Input",
  "setup.output": "Output",
  "setup.inputText": "Text",
  "setup.inputMic": "Microphone",
  "setup.outputTextOnly": "Text",
  "setup.outputAudioText": "Audio and text",
  "setup.languageEnglish": "English",
  "setup.languageJapanese": "Japanese",
  "setup.enter": "Enter conversation",
  "setup.preparing": "Preparing topic...",

  "interrupted.eyebrow": "Connection lost",
  "interrupted.title": "Your conversation was interrupted",
  "interrupted.body": "The connection seems unstable. You can try reconnecting, or see feedback for the conversation so far.",
  "interrupted.retry": "Reconnect",
  "interrupted.evaluate": "See feedback so far",
  "interrupted.evaluateBusy": "Preparing feedback...",
  "interrupted.goHome": "Go back home",

  "congestion.eyebrow": "Server is busy",
  "congestion.title": "We're at capacity right now",
  "congestion.body": "Too many conversations are running at the moment. Please wait a moment and try again.",
  "congestion.retry": "Try again",

  "conversation.eyebrow": "Live session",
  "conversation.fallbackTitle": "Conversation",
  "conversation.end": "End session",
  "conversation.ending": "Ending...",
  "conversation.you": "You",
  "conversation.statusConnecting": "Connecting...",
  "conversation.statusRecording": "Recording — tap the mic again to send",
  "conversation.statusThinking": "Thinking...",
  "conversation.statusSpeaking": "{name} is speaking",
  "conversation.statusYourTurn": "Your turn",
  "conversation.timeWarning": "About {minutes} more minute(s) left in this session.",
  "conversation.prompts": "Conversation prompts",
  "conversation.jumpIn": "Jump in",
  "conversation.placeholder": "Write what you want to say",
  "conversation.send": "Send",
  "conversation.readySystemMessage": "The conversation is ready. Say hello when you are ready.",
  "conversation.errorContinue": "The conversation couldn't continue.",
  "conversation.errorMic": "Couldn't use the microphone. Check your browser permissions.",
  "conversation.errorConnect": "Couldn't connect to the conversation.",

  "review.eyebrow": "Session review",
  "review.communication": "Communication",
  "review.language": "Language",
  "review.talkedWith": "You talked with",
  "review.noGrammarFeedback": "No grammar feedback this time.",
  "review.turns": "{count} of your turns",
  "review.questions": "{count} questions asked",
  "review.duration": "{minutes} min session",
  "review.newSession": "Start another session",
  "review.goHome": "Back to recent sessions",

  "recentSessions.title": "Look back at your recent conversations",
  "recentSessions.empty": "No reviewable sessions on this browser yet.",
  "recentSessions.errorLoad": "Couldn't load the review.",
  "recentSessions.sessionLabel": "Session {id}",
  "recentSessions.open": "View",
  "recentSessions.close": "Close",
};

const ja: Record<keyof typeof en, string> = {
  "app.recentSessions": "最近のセッション",
  "app.loading": "読み込み中…",
  "app.confirmLeaveSession": "会話中です。移動すると接続が切れます。よろしいですか？",
  "app.error.sessionExpired": "このセッションの復習期限が切れています。",
  "app.error.topicsFailed": "トピックの取得に失敗しました。",
  "app.error.sessionRestoreFailed": "セッション情報を復元できませんでした。",
  "app.error.loginFailed": "認証に失敗しました。",
  "app.error.topicPackFailed": "Topic Packの生成に失敗しました。",
  "app.error.sessionStartFailed": "セッションを開始できませんでした。",
  "app.error.reviewFailed": "Reviewを生成できませんでした。",

  "stepper.setup": "準備",
  "stepper.conversation": "会話",
  "stepper.review": "振り返り",

  "auth.eyebrow": "グループ英会話練習",
  "auth.headline1": "会話に参加しよう、",
  "auth.headline2": "授業じゃなくて。",
  "auth.subhead": "何人かのAIペルソナが自然に会話を続けます。準備ができたら話しかけて、あとで振り返りを見てみましょう。",
  "auth.username": "ユーザー名",
  "auth.password": "パスワード",
  "auth.submit": "はじめる",
  "auth.submitBusy": "サインイン中...",
  "auth.mockHint": "モックモードでは、空でない値ならどんな入力でもログインできます。",

  "setup.eyebrow": "舞台を整える",
  "setup.title": "トピックを選んで会話に参加しましょう。",
  "setup.topicLegend": "トピック",
  "setup.topicLoading": "Xの最新トレンドからトピックを生成中です…",
  "setup.loadTopics": "トレンドを読み込む",
  "setup.reloadTopics": "トレンドを更新",
  "setup.topicEmpty": "まだトピックが読み込まれていません。地域を選んで「トレンドを読み込む」を押してください。",
  "setup.region": "トレンド地域",
  "setup.regionJapan": "日本",
  "setup.regionTokyo": "東京",
  "setup.regionWorldwide": "世界",
  "setup.personaHeading": "参加するかもしれない相手",
  "setup.personaSub": "このうち{count}人がセッションごとにランダムで参加します。",
  "setup.aiVoices": "AIの参加人数",
  "setup.language": "会話の言語",
  "setup.input": "入力方法",
  "setup.output": "出力形式",
  "setup.inputText": "テキスト",
  "setup.inputMic": "マイク",
  "setup.outputTextOnly": "テキスト",
  "setup.outputAudioText": "音声とテキスト",
  "setup.languageEnglish": "英語",
  "setup.languageJapanese": "日本語",
  "setup.enter": "会話に入る",
  "setup.preparing": "トピックを準備中...",

  "interrupted.eyebrow": "接続が切れました",
  "interrupted.title": "会話が中断されました",
  "interrupted.body": "接続が不安定なようです。もう一度接続するか、ここまでの内容で振り返りを見ることができます。",
  "interrupted.retry": "もう一度接続する",
  "interrupted.evaluate": "ここまでの内容で評価を見る",
  "interrupted.evaluateBusy": "評価を作成中...",
  "interrupted.goHome": "ホームへ戻る",

  "congestion.eyebrow": "混雑しています",
  "congestion.title": "現在アクセスが集中しています",
  "congestion.body": "同時に多くの会話セッションが行われているようです。しばらく時間をおいてから、もう一度お試しください。",
  "congestion.retry": "もう一度試す",

  "conversation.eyebrow": "ライブセッション",
  "conversation.fallbackTitle": "会話",
  "conversation.end": "会話を終了",
  "conversation.ending": "終了中...",
  "conversation.you": "あなた",
  "conversation.statusConnecting": "接続中...",
  "conversation.statusRecording": "録音中 — もう一度タップで送信",
  "conversation.statusThinking": "考え中...",
  "conversation.statusSpeaking": "{name}が話しています",
  "conversation.statusYourTurn": "あなたの番です",
  "conversation.timeWarning": "このセッションは残り約{minutes}分です。",
  "conversation.prompts": "会話のヒント",
  "conversation.jumpIn": "割り込む",
  "conversation.placeholder": "話したいことを入力",
  "conversation.send": "送信",
  "conversation.readySystemMessage": "準備ができました。話す準備ができたら挨拶しましょう。",
  "conversation.errorContinue": "会話を継続できませんでした。",
  "conversation.errorMic": "マイクを利用できませんでした。ブラウザの権限を確認してください。",
  "conversation.errorConnect": "会話に接続できませんでした。",

  "review.eyebrow": "セッションの振り返り",
  "review.communication": "コミュニケーション",
  "review.language": "言語",
  "review.talkedWith": "会話した相手",
  "review.noGrammarFeedback": "今回は文法フィードバックはありません。",
  "review.turns": "あなたの発言 {count}回",
  "review.questions": "質問 {count}回",
  "review.duration": "{minutes}分のセッション",
  "review.newSession": "もう一度会話する",
  "review.goHome": "最近のセッションへ戻る",

  "recentSessions.title": "直近の会話を振り返る",
  "recentSessions.empty": "このブラウザで復習できるセッションはまだありません。",
  "recentSessions.errorLoad": "復習データを取得できませんでした。",
  "recentSessions.sessionLabel": "セッション {id}",
  "recentSessions.open": "見る",
  "recentSessions.close": "閉じる",
};

const translations: Record<Locale, Record<keyof typeof en, string>> = { en, ja };
export type TranslationKey = keyof typeof en;

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in vars ? String(vars[key]) : match));
}

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
};

export const LocaleContext = createContext<LocaleContextValue | null>(null);

export function translate(locale: Locale, key: TranslationKey, vars?: Record<string, string | number>): string {
  return interpolate(translations[locale][key], vars);
}

export function readStoredLocale(): Locale {
  return localeStorage.get() === "en" ? "en" : "ja";
}

export function useT(): LocaleContextValue["t"] {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useT must be used within LocaleContext.Provider");
  return ctx.t;
}

export function useLocale(): [Locale, (locale: Locale) => void] {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleContext.Provider");
  return [ctx.locale, ctx.setLocale];
}
