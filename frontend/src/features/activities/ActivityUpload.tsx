import { useRef, useState, type DragEvent } from "react";
import { CircleAlert, CircleCheck, CircleDashed, Copy, FileUp, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ApiError } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { Button, Card, ProgressBar } from "../../components/ui";
import { screenFiles, settle, summarize, type ItemStatus, type UploadItem } from "./uploadQueue";
import { useUploadActivityFile } from "./useActivities";

const ICONS: Record<ItemStatus, typeof CircleCheck> = {
  queued: CircleDashed,
  uploading: LoaderCircle,
  created: CircleCheck,
  duplicate: Copy,
  failed: CircleAlert,
};

// The server limits uploads per minute; when it says so, wait and go on.
const RATE_LIMIT_WAIT_MS = 8000;
const RATE_LIMIT_RETRIES = 4;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function ActivityUpload({ athleteId }: { athleteId: string }) {
  const { t } = useTranslation(["activities", "common"]);
  const upload = useUploadActivityFile(athleteId);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const files = useRef(new Map<string, File>());
  const pending = useRef<string[]>([]);
  const running = useRef(false);
  const input = useRef<HTMLInputElement>(null);

  const summary = summarize(items);

  async function send(file: File) {
    for (let attempt = 0; ; attempt++) {
      try {
        return await upload.mutateAsync(file);
      } catch (error) {
        if (error instanceof ApiError && error.status === 429 && attempt < RATE_LIMIT_RETRIES) {
          await wait(RATE_LIMIT_WAIT_MS);
          continue;
        }
        throw error;
      }
    }
  }

  async function drain() {
    if (running.current) return;
    running.current = true;
    try {
      for (let id = pending.current.shift(); id !== undefined; id = pending.current.shift()) {
        const file = files.current.get(id);
        if (!file) continue;
        setItems((current) => settle(current, id, { status: "uploading" }));
        try {
          const result = await send(file);
          setItems((current) =>
            settle(current, id, { status: result.status, error: result.error ?? undefined, activity: result.activity ?? undefined }),
          );
        } catch (error) {
          setItems((current) => settle(current, id, { status: "failed", error: errorMessage(error) }));
        }
        files.current.delete(id);
      }
    } finally {
      running.current = false;
    }
  }

  function addFiles(list: FileList | File[]) {
    const incoming = Array.from(list);
    const { accepted, rejected } = screenFiles(incoming);
    const stamp = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const next: UploadItem[] = incoming.map((file, index) => {
      const id = `${stamp}-${index}`;
      const rejection = rejected.find((r) => r.index === index);
      if (rejection) return { id, name: file.name, size: file.size, status: "failed", error: t(`upload.reject.${rejection.reason}`) };
      files.current.set(id, file);
      pending.current.push(id);
      return { id, name: file.name, size: file.size, status: "queued" };
    });
    if (accepted.length + rejected.length === 0) return;
    setItems((current) => [...next, ...current]);
    void drain();
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    addFiles(event.dataTransfer.files);
  }

  return (
    <Card eyebrow="FIT · TCX · GPX" title={t("upload.title")} actions={<FileUp className="import-source__icon" aria-hidden />}>
      <p className="ui-card__hint">{t("upload.description")}</p>

      <div
        className={dragging ? "dropzone dropzone--active" : "dropzone"}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <FileUp className="dropzone__icon" aria-hidden />
        <span className="dropzone__title">{dragging ? t("upload.dropActive") : t("upload.drop")}</span>
        <span className="dropzone__hint">{t("upload.or")}</span>
        <Button variant="secondary" size="sm" onClick={() => input.current?.click()}>
          {t("upload.browse")}
        </Button>
        <span className="dropzone__hint">{t("upload.accepted")}</span>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          accept=".fit,.tcx,.gpx"
          aria-label={t("upload.browse")}
          onChange={(event) => {
            if (event.target.files) addFiles(event.target.files);
            event.target.value = "";
          }}
        />
      </div>

      {items.length > 0 && (
        <>
          <div className="upload-summary">
            <ProgressBar value={summary.fraction} label={t("upload.progress", { done: summary.finished, total: summary.total })} />
            <div className="upload-summary__line" aria-live="polite">
              <span>{t("upload.progress", { done: summary.finished, total: summary.total })}</span>
              {!summary.busy && (
                <span>
                  {[
                    summary.created > 0 && t("upload.result_created", { count: summary.created }),
                    summary.duplicates > 0 && t("upload.result_duplicates", { count: summary.duplicates }),
                    summary.failed > 0 && t("upload.result_failed", { count: summary.failed }),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              )}
              {!summary.busy && (
                <Button variant="ghost" size="sm" onClick={() => setItems([])}>
                  {t("upload.clear")}
                </Button>
              )}
            </div>
          </div>
          <ul className="upload-list">
            {items.map((item) => {
              const Icon = ICONS[item.status];
              return (
                <li key={item.id} className={`upload-list__row upload-list__row--${item.status}`}>
                  <Icon aria-hidden className={item.status === "uploading" ? "upload-list__icon upload-list__spinner" : "upload-list__icon"} />
                  <span>
                    <span className="upload-list__name">{item.name}</span>
                    <span className={item.status === "failed" ? "upload-list__detail upload-list__detail--error" : "upload-list__detail"}>
                      {item.status === "failed" && item.error ? item.error : t(`upload.status.${item.status}`)}
                    </span>
                  </span>
                  {item.activity && (item.status === "created" || item.status === "duplicate") && (
                    <Link to={`/activities/${item.activity.id}`}>{t("upload.open")}</Link>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Card>
  );
}
