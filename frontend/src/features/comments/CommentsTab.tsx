import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { MessageSquare, Pencil, Send, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../api/errors";
import { Avatar, Badge, Button, Card, ConfirmDialog, EmptyState, IconButton, SkeletonGroup, Textarea, useToast } from "../../components/ui";
import { useFormat } from "../../i18n/useFormat";
import { MAX_COMMENT_LENGTH, type SessionComment } from "./types";
import { useAddComment, useComments, useDeleteComment, useEditComment, useMarkThreadRead } from "./useComments";
import "./Comments.css";

function CommentView({
  comment,
  onEdit,
  onDelete,
}: {
  comment: SessionComment;
  onEdit: (comment: SessionComment) => void;
  onDelete: (comment: SessionComment) => void;
}) {
  const { t } = useTranslation("training");
  const fmt = useFormat();
  return (
    <li className="comment">
      <Avatar name={comment.author_name ?? "?"} size="sm" />
      <div className="comment__main">
        <div className="comment__head">
          <strong className="comment__author">{comment.author_name ?? t("comments.formerMember")}</strong>
          <Badge tone={comment.by_athlete ? "neutral" : "accent"}>
            {comment.by_athlete ? t("comments.athlete") : t("comments.coach")}
          </Badge>
          <time className="comment__when" dateTime={comment.created_at} title={`${fmt.date(comment.created_at, "medium")} ${fmt.time(comment.created_at)}`}>
            {fmt.relative(comment.created_at)}
          </time>
          {comment.edited_at && <span className="comment__when">{t("comments.edited")}</span>}
        </div>
        <p className="comment__body">{comment.body}</p>
      </div>
      <span className="comment__actions">
        {comment.can_edit && (
          <IconButton aria-label={t("comments.edit")} size="sm" onClick={() => onEdit(comment)}>
            <Pencil aria-hidden />
          </IconButton>
        )}
        {comment.can_delete && (
          <IconButton aria-label={t("comments.delete")} size="sm" onClick={() => onDelete(comment)}>
            <Trash2 aria-hidden />
          </IconButton>
        )}
      </span>
    </li>
  );
}

/** The discussion on one athlete's session: the athlete, their coaches and club admins. */
export function CommentsTab({ athleteId, eventId }: { athleteId: string; eventId: string }) {
  const { t } = useTranslation("training");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const comments = useComments(athleteId, eventId);
  const add = useAddComment(athleteId, eventId);
  const edit = useEditComment(athleteId, eventId);
  const remove = useDeleteComment(athleteId, eventId);
  const { mutate: markRead } = useMarkThreadRead(athleteId, eventId);
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<SessionComment | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [deleting, setDeleting] = useState<SessionComment | null>(null);

  // Showing the thread reads it: tell the server up to the newest comment by someone else.
  const newest = comments.data?.at(-1)?.id;
  const hasOthers = comments.data?.some((comment) => !comment.can_edit) ?? false;
  useEffect(() => {
    if (newest !== undefined && hasOthers) markRead();
  }, [newest, hasOthers, markRead]);

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const body = draft.trim();
    if (!body) return;
    try {
      await add.mutateAsync(body);
      setDraft("");
    } catch {
      // shown under the composer
    }
  }

  function onComposerKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void send();
    }
  }

  async function saveEdit() {
    if (!editing) return;
    try {
      await edit.mutateAsync({ id: editing.id, body: editDraft.trim() });
      setEditing(null);
    } catch (error) {
      toast({ title: errorMessage(error), tone: "error" });
    }
  }

  return (
    <Card as="section" title={t("comments.title")}>
      <div className="comments">
        {comments.isLoading && <SkeletonGroup lines={3} />}
        {comments.isError && <p role="alert">{tc("loadError")}</p>}
        {comments.data && comments.data.length === 0 && (
          <EmptyState compact icon={<MessageSquare aria-hidden />} title={t("comments.emptyTitle")} description={t("comments.emptyDescription")} />
        )}
        {comments.data && comments.data.length > 0 && (
          <ol className="comments__list">
            {comments.data.map((comment) =>
              editing?.id === comment.id ? (
                <li key={comment.id} className="comment comment--editing">
                  <Textarea
                    label={t("comments.edit")}
                    value={editDraft}
                    rows={3}
                    maxLength={MAX_COMMENT_LENGTH}
                    autoFocus
                    onChange={(e) => setEditDraft(e.target.value)}
                  />
                  <div className="comments__buttons">
                    <Button variant="ghost" size="sm" onClick={() => setEditing(null)}>
                      {tc("cancel")}
                    </Button>
                    <Button size="sm" loading={edit.isPending} disabled={editDraft.trim() === "" || editDraft.trim() === comment.body} onClick={saveEdit}>
                      {tc("save")}
                    </Button>
                  </div>
                </li>
              ) : (
                <CommentView
                  key={comment.id}
                  comment={comment}
                  onEdit={(c) => {
                    setEditing(c);
                    setEditDraft(c.body);
                  }}
                  onDelete={setDeleting}
                />
              ),
            )}
          </ol>
        )}

        <form className="comments__composer" onSubmit={send}>
          <Textarea
            label={t("comments.write")}
            value={draft}
            rows={3}
            maxLength={MAX_COMMENT_LENGTH}
            placeholder={t("comments.placeholder")}
            hint={t("comments.shortcut")}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onComposerKey}
          />
          {add.isError && <p role="alert">{errorMessage(add.error, { 429: t("comments.tooFast") })}</p>}
          <div className="comments__buttons">
            <Button type="submit" icon={<Send aria-hidden />} loading={add.isPending} disabled={draft.trim() === ""}>
              {t("comments.send")}
            </Button>
          </div>
        </form>
      </div>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        tone="danger"
        title={t("comments.deleteTitle")}
        description={t("comments.deleteDescription")}
        confirmLabel={tc("delete")}
        cancelLabel={tc("cancel")}
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await remove.mutateAsync(deleting.id);
          } catch (error) {
            toast({ title: errorMessage(error), tone: "error" });
            throw error;
          }
        }}
      />
    </Card>
  );
}
