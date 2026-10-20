import { describe, expect, it } from "vitest";
import { MAX_FILE_BYTES, extensionOf, screenFiles, settle, summarize, type UploadItem } from "./uploadQueue";

const item = (id: string, status: UploadItem["status"]): UploadItem => ({ id, name: `${id}.fit`, size: 1000, status });

describe("screenFiles", () => {
  it("accepts FIT, TCX and GPX in any letter case and turns the rest away", () => {
    const { accepted, rejected } = screenFiles([
      { name: "ride.fit", size: 10 },
      { name: "RIDE.TCX", size: 10 },
      { name: "track.Gpx", size: 10 },
      { name: "notes.txt", size: 10 },
      { name: "archive.fit.gz", size: 10 },
      { name: "noextension", size: 10 },
    ]);
    expect(accepted).toEqual([0, 1, 2]);
    expect(rejected).toEqual([
      { index: 3, reason: "extension" },
      { index: 4, reason: "extension" },
      { index: 5, reason: "extension" },
    ]);
  });

  it("rejects files over the server's size limit", () => {
    const { accepted, rejected } = screenFiles([
      { name: "ok.fit", size: MAX_FILE_BYTES },
      { name: "big.fit", size: MAX_FILE_BYTES + 1 },
    ]);
    expect(accepted).toEqual([0]);
    expect(rejected).toEqual([{ index: 1, reason: "size" }]);
  });

  it("finds extensions", () => {
    expect(extensionOf("a.b.FIT")).toBe(".fit");
    expect(extensionOf("none")).toBe("");
  });
});

describe("queue state", () => {
  it("settles one item without touching the others", () => {
    const items = [item("a", "queued"), item("b", "queued")];
    const next = settle(items, "a", { status: "failed", error: "bad file" });
    expect(next[0]).toMatchObject({ status: "failed", error: "bad file" });
    expect(next[1]).toBe(items[1]);
  });

  it("summarizes progress by finished files", () => {
    const summary = summarize([item("a", "created"), item("b", "duplicate"), item("c", "failed"), item("d", "uploading"), item("e", "queued")]);
    expect(summary).toMatchObject({ total: 5, finished: 3, created: 1, duplicates: 1, failed: 1, busy: true });
    expect(summary.fraction).toBeCloseTo(0.6);
  });

  it("is idle and empty when nothing is queued", () => {
    expect(summarize([])).toMatchObject({ total: 0, fraction: 0, busy: false });
    expect(summarize([item("a", "created")])).toMatchObject({ fraction: 1, busy: false });
  });
});
