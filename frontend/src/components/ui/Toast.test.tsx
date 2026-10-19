import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "./Toast";
import { useToast } from "./useToast";

function Trigger() {
  const { toast } = useToast();
  return (
    <button type="button" onClick={() => toast({ title: "Synced", description: "12 new laps", tone: "success" })}>
      go
    </button>
  );
}

describe("useToast", () => {
  it("shows a toast with title and description", async () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "go" }));
    expect(await screen.findByText("Synced")).toBeInTheDocument();
    expect(screen.getByText("12 new laps")).toBeInTheDocument();
  });

  it("throws a clear error outside the provider", () => {
    expect(() => render(<Trigger />)).toThrow(/ToastProvider/);
  });
});
