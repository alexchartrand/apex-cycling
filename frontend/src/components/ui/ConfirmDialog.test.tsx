import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

function Harness({ onConfirm }: { onConfirm: () => Promise<void> }) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <span data-testid="state">{open ? "open" : "closed"}</span>
      <ConfirmDialog open={open} onOpenChange={setOpen} title="Delete lap?" confirmLabel="Delete" tone="danger" onConfirm={onConfirm} />
    </>
  );
}

describe("ConfirmDialog", () => {
  it("closes after onConfirm resolves", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);
    render(<Harness onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.getByTestId("state")).toHaveTextContent("closed"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("stays open when onConfirm rejects", async () => {
    render(<Harness onConfirm={() => Promise.reject(new Error("nope"))} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Delete" })).not.toBeDisabled());
    expect(screen.getByTestId("state")).toHaveTextContent("open");
  });

  it("cancel closes without confirming", async () => {
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByTestId("state")).toHaveTextContent("closed");
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
