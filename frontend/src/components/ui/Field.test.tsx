import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { initialsOf } from "./initials";
import { Input } from "./Field";

describe("Input", () => {
  it("links the label and describes the control with its hint", () => {
    render(<Input label="Weight" hint="Used for W/kg" suffix="kg" />);
    const input = screen.getByLabelText("Weight");
    expect(input).toHaveAccessibleDescription("Used for W/kg");
    expect(screen.getByText("kg")).toBeInTheDocument();
  });

  it("marks the control invalid and announces the error instead of the hint", () => {
    render(<Input label="Weight" hint="Used for W/kg" error="Must be positive" />);
    const input = screen.getByLabelText("Weight");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Must be positive");
    expect(screen.queryByText("Used for W/kg")).not.toBeInTheDocument();
  });

  it("renders a bare input when no chrome is given", () => {
    const { container } = render(<Input aria-label="Search" />);
    expect(container.querySelector(".field")).toBeNull();
  });
});

describe("initialsOf", () => {
  it.each([
    ["Camille Lavoie", "CL"],
    ["Jean-Marc de la Fontaine", "JF"],
    ["  madonna  ", "MA"],
    ["", "?"],
  ])("%s → %s", (name, expected) => {
    expect(initialsOf(name)).toBe(expected);
  });
});
