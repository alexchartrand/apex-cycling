import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { FileText, MessageSquare, Plus, RefreshCcw, Send, Sparkles, Target, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { aiErrorText } from "./aiErrors";
import { Button, ConfirmDialog, EmptyState, IconButton, SkeletonGroup, Textarea } from "../../components/ui";
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
function LiveMessage({ live }: { live: LiveReply }) {
  const { t } = useTranslation("aicoach");
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
      </div>
    </li>
  );
}

/** The conversation list, then the open conversation with its composer. */
export function ChatPanel({
  athleteId,
  conversationId,
  onOpen,
}: {
  athleteId: string;
  conversationId: string | null;
  onOpen: (id: string | null) => void;
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
  const [toDelete, setToDelete] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const busy = start.isPending || send.isPending;
  const error = start.error ?? send.error;
  const live = start.live ?? send.live;
  // Follows the reply as it grows, a few lines at a time rather than on every piece.
  const liveStep = live ? Math.floor(live.text.length / 160) : -1;

  const messages = conversation.data?.messages ?? [];
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages.length, busy, liveStep]);

  function submit(text: string) {
    const content = text.trim();
    if (!content || busy) return;
    setPendingText(content);
    const done = { onSettled: () => setPendingText(null) };
    if (conversationId) {
      send.mutate({ conversationId, content }, { ...done, onSuccess: () => setDraft("") });
    } else {
      start.mutate({ kind: "chat", content }, { ...done, onSuccess: (turn) => (setDraft(""), onOpen(turn.conversation_id)) });
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

  function buildPlan() {
    start.mutate({ kind: "intake" }, { onSuccess: (turn) => onOpen(turn.conversation_id) });
  }

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
                    <span className="ai-muted">{fmt.relative(item.updated_at ?? item.created_at)}</span>
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
        {conversationId === null && !busy && (
          <EmptyState
            icon={<Sparkles aria-hidden />}
            title={t("chat.welcome")}
            description={t("chat.welcomeHint")}
            action={
              <div className="ai-chat__starts">
                <Button icon={<Target aria-hidden />} onClick={buildPlan}>
                  {t("chat.buildPlan")}
                </Button>
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
          {busy && pendingText && (
            <li className="ai-message ai-message--user">
              <div className="ai-message__bubble">
                <p>{pendingText}</p>
              </div>
            </li>
          )}
          {busy && <LiveMessage live={live ?? LIVE_START} />}
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
