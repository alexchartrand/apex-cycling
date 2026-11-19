import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { FileText, MessageSquare, Plus, RefreshCcw, Send, Sparkles, Target, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { aiErrorText } from "./aiErrors";
import { Button, ButtonLink, ConfirmDialog, EmptyState, IconButton, SkeletonGroup, Textarea } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { Markdown } from "./Markdown";
import { ProposalCard } from "./ProposalCard";
import { LIVE_START, type LiveReply } from "./turnStream";
import type { AiMessage, ConversationKind } from "./types";
import { useConversation, useConversations, useDeleteConversation, useSendMessage, useStartConversation } from "./useAiCoach";

const KIND_ICON = { chat: MessageSquare, intake: Target, report: FileText, replan: RefreshCcw } as const satisfies Record<
  ConversationKind,
  unknown
>;

const SUGGESTIONS = ["form", "shortDay", "lighter", "explain"] as const;

function Message({ athleteId, message }: { athleteId: string; message: AiMessage }) {
  return (
    <li className={`ai-message ai-message--${message.role}`}>
      {message.content && (
        <div className="ai-message__bubble">
          {message.role === "assistant" ? <Markdown text={message.content} /> : <p>{message.content}</p>}
        </div>
      )}
      {message.proposal && <ProposalCard athleteId={athleteId} proposal={message.proposal} compact />}
    </li>
  );
}

type Status = "calendar" | "training" | "fitness" | "library" | "profile" | "proposal" | "data";

const TOOL_STATUS: Record<string, Status> = {
  get_plans: "calendar",
  get_training: "training",
  get_session_efforts: "training",
  get_training_load: "fitness",
  get_power_profile: "fitness",
  list_workouts: "library",
  get_workout: "library",
  save_profile: "profile",
  propose_changes: "proposal",
};

/** The reply being written: its text so far, else what the coach is doing. */
function LiveMessage({ live, since }: { live: LiveReply; since: number }) {
  const { t } = useTranslation("aicoach");
  const elapsed = useElapsedSeconds(since);
  if (live.text) {
    return (
      <li className="ai-message ai-message--assistant">
        <div className="ai-message__bubble ai-message__bubble--live">
          <Markdown text={live.text} />
        </div>
      </li>
    );
  }
  const label =
    live.phase === "tool" && live.tool ? t(`chat.status.${TOOL_STATUS[live.tool] ?? "data"}`) : t("chat.thinking");
  return (
    <li className="ai-message ai-message--assistant">
      <div className="ai-message__bubble ai-message__bubble--thinking" role="status">
        <span className="ai-dots" aria-hidden>
          <span />
          <span />
          <span />
        </span>
        {label}
        {/* A plan proposal can reason silently for minutes: show it hasn't frozen. */}
        {elapsed >= SHOW_ELAPSED_AFTER_S && (
          <span className="ai-muted ai-message__elapsed">{t("chat.elapsed", { time: clockText(elapsed) })}</span>
        )}
      </div>
    </li>
  );
}

const SHOW_ELAPSED_AFTER_S = 15;

function clockText(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function useElapsedSeconds(since: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return Math.max(0, Math.floor((now - since) / 1000));
}

/** The conversation list, then the open conversation with its composer. */
export function ChatPanel({
  athleteId,
  conversationId,
  onOpen,
  build = null,
  onBuildStarted,
}: {
  athleteId: string;
  conversationId: string | null;
  onOpen: (id: string | null) => void;
  /** Start building a plan on arrival: "new", or the id of the training plan to fill. */
  build?: string | null;
  /** Called as the `build` intake starts, so the page drops `build` from its URL and a remount can't start it again. */
  onBuildStarted?: () => void;
}) {
  const { t } = useTranslation(["aicoach", "common"]);
  const fmt = useFormat();
  const conversations = useConversations(athleteId);
  const conversation = useConversation(athleteId, conversationId);
  const start = useStartConversation(athleteId);
  const send = useSendMessage(athleteId);
  const remove = useDeleteConversation(athleteId);
  const [draft, setDraft] = useState("");
  const [pendingText, setPendingText] = useState<string | null>(null);
  // The conversation the turn in flight belongs to (null: one being started), so its
  // live reply shows there and not in whichever conversation is open meanwhile.
  const [turn, setTurn] = useState<{ conversationId: string | null; since: number } | null>(null);
  const [toDelete, setToDelete] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const busy = start.isPending || send.isPending;
  const error = start.error ?? send.error;
  const live = start.live ?? send.live;
  const turnHere = busy && (turn === null || turn.conversationId === conversationId);
  // Follows the reply as it grows, a few lines at a time rather than on every piece.
  const liveStep = live ? Math.floor(live.text.length / 160) : -1;

  const messages = conversation.data?.messages ?? [];
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages.length, turnHere, liveStep]);

  function submit(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    setPendingText(content);
    setTurn({ conversationId, since: Date.now() });
    // The box empties as soon as the message is sent; a failed turn gives the text back
    // unless something new was typed meanwhile.
    setDraft("");
    const done = {
      onSettled: () => (setPendingText(null), setTurn(null)),
      onError: () => setDraft((current) => current || text),
    };
    if (conversationId) {
      send.mutate({ conversationId, content }, done);
    } else {
      start.mutate({ kind: "chat", content }, { ...done, onSuccess: (turn) => onOpen(turn.conversation_id) });
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit(draft);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit(draft);
    }
  }

  function buildPlan(trainingPlanId?: string) {
    setTurn({ conversationId: null, since: Date.now() });
    start.mutate(
      { kind: "intake", ...(trainingPlanId ? { training_plan_id: trainingPlanId } : {}) },
      { onSuccess: (done) => onOpen(done.conversation_id), onSettled: () => setTurn(null) },
    );
  }

  // Arriving from a plan's "Ask the AI coach" (`?build=`): start once. Not straight from
  // the effect: StrictMode's unmount/remount of a fresh mount detaches TanStack's mutation
  // observer from a mutation started in between, so the panel would never see the turn end
  // (stuck "thinking", composer disabled). The timeout fires after that double run, the ref
  // covers a re-run, and the page clearing `build` covers a real remount.
  const built = useRef<string | null>(null);
  useEffect(() => {
    if (!build || built.current === build) return;
    const timer = setTimeout(() => {
      built.current = build;
      buildPlan(build === "new" ? undefined : build);
      onBuildStarted?.();
    }, 0);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per `build` value
  }, [build]);

  return (
    <div className="ai-chat">
      <aside className="ai-chat__list" aria-label={t("chat.history")}>
        <Button variant="secondary" size="sm" icon={<Plus aria-hidden />} onClick={() => onOpen(null)} block>
          {t("chat.new")}
        </Button>
        {conversations.isLoading ? (
          <SkeletonGroup lines={3} />
        ) : (
          <ul>
            {(conversations.data ?? []).map((item) => {
              const Icon = KIND_ICON[item.kind];
              return (
                <li key={item.id} className={item.id === conversationId ? "ai-chat__entry ai-chat__entry--active" : "ai-chat__entry"}>
                  <button type="button" onClick={() => onOpen(item.id)}>
                    <Icon aria-hidden className="ai-inline-icon" />
                    <span className="ai-chat__entry-title">{item.title ?? t(`chat.kinds.${item.kind}`)}</span>
                    <span className="ai-muted">
                      {busy && turn?.conversationId === item.id
                        ? t("chat.replying")
                        : fmt.relative(item.updated_at ?? item.created_at)}
                    </span>
                  </button>
                  <IconButton aria-label={t("chat.delete")} size="sm" variant="ghost" onClick={() => setToDelete(item.id)}>
                    <Trash2 aria-hidden />
                  </IconButton>
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      <section className="ai-chat__main" aria-label={t("chat.conversation")}>
        {conversationId === null && !turnHere && (
          <EmptyState
            icon={<Sparkles aria-hidden />}
            title={t("chat.welcome")}
            description={t("chat.welcomeHint")}
            action={
              <div className="ai-chat__starts">
                {/* The plan's sport, goal and dates are asked first, on the plan form; the intake then builds on it. */}
                <ButtonLink to="/plans/new?ai=chat" icon={<Target aria-hidden />}>
                  {t("chat.buildPlan")}
                </ButtonLink>
                <div className="ai-chat__suggestions">
                  {SUGGESTIONS.map((key) => (
                    <button key={key} type="button" className="ai-chip" onClick={() => submit(t(`chat.suggestions.${key}`))}>
                      {t(`chat.suggestions.${key}`)}
                    </button>
                  ))}
                </div>
              </div>
            }
          />
        )}
        {conversationId !== null && conversation.isLoading && <SkeletonGroup lines={4} />}
        <ol className="ai-chat__messages">
          {messages.map((message) => (
            <Message key={message.id} athleteId={athleteId} message={message} />
          ))}
          {turnHere && pendingText && (
            <li className="ai-message ai-message--user">
              <div className="ai-message__bubble">
                <p>{pendingText}</p>
              </div>
            </li>
          )}
          {turnHere && <LiveMessage live={live ?? LIVE_START} since={turn?.since ?? Date.now()} />}
        </ol>
        <div ref={endRef} />
        {error && <p className="ai-error" role="alert">{aiErrorText(error, t)}</p>}

        <form className="ai-chat__composer" onSubmit={onSubmit}>
          <Textarea
            aria-label={t("chat.placeholder")}
            placeholder={t("chat.placeholder")}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            maxLength={4000}
            disabled={busy}
          />
          <IconButton type="submit" aria-label={t("chat.send")} disabled={busy || !draft.trim()}>
            <Send aria-hidden />
          </IconButton>
        </form>
        <p className="ai-muted ai-chat__disclaimer">{t("chat.disclaimer")}</p>
      </section>

      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title={t("chat.deleteTitle")}
        description={t("chat.deleteHint")}
        confirmLabel={t("chat.delete")}
        cancelLabel={t("common:cancel")}
        tone="danger"
        onConfirm={() => {
          if (!toDelete) return;
          remove.mutate(toDelete, { onSuccess: () => toDelete === conversationId && onOpen(null) });
          setToDelete(null);
        }}
      />
    </div>
  );
}
