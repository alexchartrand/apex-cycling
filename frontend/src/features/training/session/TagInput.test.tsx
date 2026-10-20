import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { TagInput } from "./TagInput";
import { addTag, MAX_TAG_LENGTH, MAX_TAGS } from "./tags";

describe("addTag", () => {
  it("trims, ignores blanks and case-insensitive duplicates", () => {
    expect(addTag(["Track"], "  openers ")).toEqual(["Track", "openers"]);
    expect(addTag(["Track"], "track")).toEqual(["Track"]);
    expect(addTag(["Track"], "   ")).toEqual(["Track"]);
  });

  it("caps the tag length and the number of tags", () => {
    expect(addTag([], "x".repeat(MAX_TAG_LENGTH + 5))[0]).toHaveLength(MAX_TAG_LENGTH);
    const full = Array.from({ length: MAX_TAGS }, (_, i) => `t${i}`);
    expect(addTag(full, "one more")).toBe(full);
  });
});

function Harness({ initial = [] as string[] }) {
  const [tags, setTags] = useState(initial);
  return <TagInput label="Tags" value={tags} onChange={setTags} />;
}

describe("TagInput", () => {
  it("adds a tag on Enter or comma and removes with its button or Backspace", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["track"]} />);
    const field = screen.getByLabelText("Tags");

    await user.type(field, "sprint{Enter}");
    await user.type(field, "kilo,");
    expect(screen.getByText("sprint")).toBeInTheDocument();
    expect(screen.getByText("kilo")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove tag sprint" }));
    expect(screen.queryByText("sprint")).not.toBeInTheDocument();

    await user.type(field, "{Backspace}"); // empty field: drops the last chip
    expect(screen.queryByText("kilo")).not.toBeInTheDocument();
    expect(screen.getByText("track")).toBeInTheDocument();
  });

  it("keeps a half-typed tag when focus leaves", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByLabelText("Tags"), "pending");
    await user.tab();
    expect(screen.getByText("pending")).toBeInTheDocument();
  });
});
