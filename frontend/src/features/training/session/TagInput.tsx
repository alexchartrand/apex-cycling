import { useId, useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { addTag, MAX_TAG_LENGTH } from "./tags";
import "./TagInput.css";

/** Free-text chips: Enter or comma adds the typed tag, Backspace on an empty field removes the last one. */
export function TagInput({ label, hint, value, onChange }: { label: string; hint?: string; value: string[]; onChange: (tags: string[]) => void }) {
  const { t } = useTranslation("training");
  const id = useId();
  const [draft, setDraft] = useState("");

  function commit() {
    if (draft.trim()) onChange(addTag(value, draft));
    setDraft("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit();
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <div className="tag-input">
        {value.map((tag) => (
          <span key={tag} className="tag-input__chip">
            {tag}
            <button type="button" className="tag-input__remove" aria-label={t("notes.removeTag", { tag })} onClick={() => onChange(value.filter((x) => x !== tag))}>
              <X aria-hidden />
            </button>
          </span>
        ))}
        <input
          id={id}
          className="tag-input__field"
          value={draft}
          maxLength={MAX_TAG_LENGTH}
          placeholder={t("notes.tagPlaceholder")}
          onChange={(e) => setDraft(e.target.value.replace(",", ""))}
          onKeyDown={onKeyDown}
          onBlur={commit}
          aria-describedby={hint ? `${id}-hint` : undefined}
        />
      </div>
      {hint && (
        <div className="field__hint" id={`${id}-hint`}>
          {hint}
        </div>
      )}
    </div>
  );
}
