import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable, type DataTableColumn } from "./DataTable";

type Lap = { id: string; n: number; ms: number | null };
const rows: Lap[] = [
  { id: "1", n: 1, ms: 18_400 },
  { id: "2", n: 2, ms: 17_900 },
  { id: "3", n: 3, ms: null },
];
const columns: DataTableColumn<Lap>[] = [
  { id: "lap", header: "Lap", cell: (r) => `Lap ${r.n}`, primary: true },
  { id: "time", header: "Time", cell: (r) => (r.ms == null ? "—" : (r.ms / 1000).toFixed(3)), sortValue: (r) => r.ms },
];

function bodyRowTexts() {
  const [, body] = screen.getAllByRole("rowgroup");
  return within(body)
    .getAllByRole("row")
    .map((row) => within(row).getAllByRole("cell")[0].textContent);
}

describe("DataTable", () => {
  it("sorts by a sortable column when its header is clicked", async () => {
    render(<DataTable caption="Laps" columns={columns} rows={rows} getRowId={(r) => r.id} />);
    expect(bodyRowTexts()).toEqual(["Lap 1", "Lap 2", "Lap 3"]);

    await userEvent.click(screen.getByRole("button", { name: /time/i }));
    expect(bodyRowTexts()).toEqual(["Lap 2", "Lap 1", "Lap 3"]);
    expect(screen.getByRole("columnheader", { name: /time/i })).toHaveAttribute("aria-sort", "ascending");
  });

  it("calls onRowClick from mouse and keyboard", async () => {
    const onRowClick = vi.fn();
    render(<DataTable caption="Laps" columns={columns} rows={rows} getRowId={(r) => r.id} onRowClick={onRowClick} />);
    const [, body] = screen.getAllByRole("rowgroup");
    const firstRow = within(body).getAllByRole("row")[0];

    await userEvent.click(firstRow);
    firstRow.focus();
    await userEvent.keyboard("{Enter}");
    expect(onRowClick).toHaveBeenCalledTimes(2);
    expect(onRowClick).toHaveBeenCalledWith(rows[0]);
  });

  it("renders cards with the primary column as heading in card layout", () => {
    render(<DataTable caption="Laps" columns={columns} rows={rows} getRowId={(r) => r.id} layout="cards" />);
    const list = screen.getByRole("list", { name: "Laps" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[1]).toHaveTextContent("Lap 2");
    expect(items[1]).toHaveTextContent("17.900");
  });

  it("shows the empty state when there are no rows", () => {
    render(<DataTable caption="Laps" columns={columns} rows={[]} getRowId={(r) => r.id} empty={<p>No laps</p>} />);
    expect(screen.getByText("No laps")).toBeInTheDocument();
  });
});
