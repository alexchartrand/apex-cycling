import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { errorMessage } from "../../../api/errors";
import { Button, Card, Input, Select, Textarea, useToast } from "../../../components/ui";
import type { SessionDetail } from "../types";
import { useUpdateSession } from "../useTraining";
import { changesFrom, draftOf } from "./notesDraft";
import { TagInput } from "./TagInput";
import "./NotesTab.css";

const RPE_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const;

export function NotesTab({ athleteId, session }: { athleteId: string; session: SessionDetail }) {
  const { t } = useTranslation("training");
  const { t: tc } = useTranslation("common");
  const { toast } = useToast();
  const mutation = useUpdateSession(athleteId, session.external_event_id);
  const [draft, setDraft] = useState(() => draftOf(session));
  const changes = changesFrom(session, draft);
  const dirty = Object.keys(changes).length > 0;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!dirty) return;
    try {
      await mutation.mutateAsync(changes);
      toast({ title: t("notes.saved"), tone: "success" });
    } catch {
      // shown below
    }
  }

  return (
    <Card as="section" title={t("session.tabs.notes")}>
      <form className="notes-tab" onSubmit={handleSubmit}>
        <Input
          label={t("notes.title")}
          hint={t("notes.titleHint", { name: session.original_name })}
          value={draft.title}
          maxLength={255}
          placeholder={session.original_name}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
        />
        <Select label={t("notes.rpe")} value={draft.rpe} onChange={(e) => setDraft({ ...draft, rpe: e.target.value })}>
          <option value="">{t("notes.rpeNone")}</option>
          {RPE_LEVELS.map((level) => (
            <option key={level} value={level}>
              {t(`notes.rpeLevels.l${level}`)}
            </option>
          ))}
        </Select>
        <Textarea
          label={t("notes.notes")}
          rows={6}
          maxLength={5000}
          placeholder={t("notes.notesPlaceholder")}
          value={draft.notes}
          onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
        />
        <TagInput label={t("notes.tags")} hint={t("notes.tagsHint")} value={draft.tags} onChange={(tags) => setDraft({ ...draft, tags })} />
        {mutation.isError && (
          <p className="notes-tab__error" role="alert">
            {errorMessage(mutation.error)}
          </p>
        )}
        <div className="notes-tab__actions">
          <Button type="submit" loading={mutation.isPending} disabled={!dirty}>
            {tc("save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
