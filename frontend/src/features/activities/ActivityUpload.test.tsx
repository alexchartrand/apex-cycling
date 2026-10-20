import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ActivityUpload } from "./ActivityUpload";

const activity = { id: "act-1", name: null, start_time: "2026-06-01T07:00:00Z" };

function reply(status: "created" | "duplicate" | "failed", error: string | null = null) {
  return new Response(JSON.stringify([{ filename: "x", status, activity: status === "failed" ? null : activity, error }]), { status: 200 });
}

describe("ActivityUpload", () => {
  const fetchMock = vi.fn();

  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  function renderUpload() {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <ActivityUpload athleteId="ath-1" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    return screen.getByLabelText("choose files") as HTMLInputElement;
  }

  const file = (name: string, size = 100) => new File([new Uint8Array(size)], name);

  it("sends each accepted file on its own and reports what happened to it", async () => {
    fetchMock.mockResolvedValueOnce(reply("created")).mockResolvedValueOnce(reply("duplicate")).mockResolvedValueOnce(reply("failed", "corrupt FIT file"));
    const input = renderUpload();

    await userEvent.upload(input, [file("a.fit"), file("b.tcx"), file("c.gpx")]);

    await waitFor(() => expect(screen.getByText("3 of 3 files")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledTimes(3);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/athletes/ath-1/activities/upload");
    expect(init.body).toBeInstanceOf(FormData);
    // The browser must choose the multipart boundary itself.
    expect(init.headers["Content-Type"]).toBeUndefined();

    expect(screen.getByText("Imported")).toBeInTheDocument();
    expect(screen.getByText("Already imported")).toBeInTheDocument();
    expect(screen.getByText("corrupt FIT file")).toBeInTheDocument();
    expect(screen.getByText("1 ride imported · 1 already there · 1 failed")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open" })).toHaveLength(2);
  });

  it("turns away files that can't be activities without contacting the server", async () => {
    const input = renderUpload();

    // `applyAccept: false`: the picker's accept filter is bypassed, as with drag and drop.
    await userEvent.setup({ applyAccept: false }).upload(input, [file("notes.txt"), file("huge.fit", 15 * 1024 * 1024 + 1)]);

    expect(await screen.findByText("Not a FIT, TCX or GPX file")).toBeInTheDocument();
    expect(screen.getByText("Larger than 15 MB")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows a failed request against the file it belonged to and goes on", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Only the athlete can change their activities" }), { status: 403 }))
      .mockResolvedValueOnce(reply("created"));
    const input = renderUpload();

    await userEvent.upload(input, [file("a.fit"), file("b.fit")]);

    await waitFor(() => expect(screen.getByText("2 of 2 files")).toBeInTheDocument());
    expect(screen.getByText("Only the athlete can change their activities")).toBeInTheDocument();
    expect(screen.getByText("Imported")).toBeInTheDocument();
  });

  it("clears the list once everything is done", async () => {
    fetchMock.mockResolvedValueOnce(reply("created"));
    const input = renderUpload();
    await userEvent.upload(input, [file("a.fit")]);
    await userEvent.click(await screen.findByRole("button", { name: "Clear list" }));
    expect(screen.queryByText("a.fit")).not.toBeInTheDocument();
  });
});
