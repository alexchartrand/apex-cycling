import type { Activity, UploadStatus } from "./types";

export const ACCEPTED_EXTENSIONS = [".fit", ".tcx", ".gpx"] as const;
/** Mirrors the server's limit per file. */
export const MAX_FILE_BYTES = 15 * 1024 * 1024;

export type ItemStatus = "queued" | "uploading" | UploadStatus;

export interface UploadItem {
  id: string;
  name: string;
  size: number;
  status: ItemStatus;
  /** Why it failed or was turned away. */
  error?: string;
  activity?: Activity;
}

export type RejectReason = "extension" | "size";

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

/** Which files go in the queue, and which are turned away before any request. */
export function screenFiles(files: { name: string; size: number }[]): {
  accepted: number[];
  rejected: { index: number; reason: RejectReason }[];
} {
  const accepted: number[] = [];
  const rejected: { index: number; reason: RejectReason }[] = [];
  files.forEach((file, index) => {
    if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(extensionOf(file.name))) rejected.push({ index, reason: "extension" });
    else if (file.size > MAX_FILE_BYTES) rejected.push({ index, reason: "size" });
    else accepted.push(index);
  });
  return { accepted, rejected };
}

export function settle(items: UploadItem[], id: string, patch: Partial<UploadItem>): UploadItem[] {
  return items.map((item) => (item.id === id ? { ...item, ...patch } : item));
}

export interface UploadSummary {
  total: number;
  finished: number;
  created: number;
  duplicates: number;
  failed: number;
  /** 0–1, for the progress bar. */
  fraction: number;
  busy: boolean;
}

export function summarize(items: UploadItem[]): UploadSummary {
  const count = (status: ItemStatus) => items.filter((item) => item.status === status).length;
  const created = count("created");
  const duplicates = count("duplicate");
  const failed = count("failed");
  const finished = created + duplicates + failed;
  return {
    total: items.length,
    finished,
    created,
    duplicates,
    failed,
    fraction: items.length === 0 ? 0 : finished / items.length,
    busy: items.some((item) => item.status === "queued" || item.status === "uploading"),
  };
}
