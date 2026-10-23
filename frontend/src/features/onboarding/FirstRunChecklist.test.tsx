import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { buildChecklist } from "./checklist";
import { FirstRunChecklist } from "./FirstRunChecklist";

function renderChecklist(input: Parameters<typeof buildChecklist>[0], onHide = vi.fn()) {
  render(
    <MemoryRouter>
      <FirstRunChecklist checklist={buildChecklist(input)} onHide={onHide} />
    </MemoryRouter>,
  );
  return onHide;
}

describe("FirstRunChecklist", () => {
  it("counts the steps done and links each open step to where it is done", () => {
    renderChecklist({ transponders: 1, weightKg: null, clubs: 0, activeCoaches: 0 });

    expect(screen.getAllByText("1 of 4").length).toBeGreaterThan(0);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    // The finished step has no link; the open ones do.
    expect(screen.queryByRole("link", { name: /Connect/ })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Add/ })).toHaveAttribute("href", "/settings/physiology");
    expect(screen.getByRole("link", { name: /Open clubs/ })).toHaveAttribute("href", "/club");
    expect(screen.getByRole("link", { name: /Find a coach/ })).toHaveAttribute("href", "/coach");
    expect(screen.getByText("Connect your transponder").textContent).toContain("done");
  });

  it("points the transponder step at the sqorz card on the import page", () => {
    renderChecklist({ transponders: 0, weightKg: null, clubs: 0, activeCoaches: 0 });
    expect(screen.getByRole("link", { name: /Connect/ })).toHaveAttribute("href", "/import#sqorz");
    expect(screen.getAllByText(/optional/)).toHaveLength(2); // club and coach
  });

  it("can be hidden", async () => {
    const onHide = renderChecklist({ transponders: 0, weightKg: null, clubs: 0, activeCoaches: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Hide this checklist" }));
    expect(onHide).toHaveBeenCalledOnce();
  });
});
