import { useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { PHONE_QUERY, useMediaQuery } from "../../hooks/useMediaQuery";
import { nextSort, sortRows, type SortDirection, type SortValue } from "./dataTableSort";
import "./DataTable.css";

export type DataTableColumn<T> = {
  id: string;
  header: ReactNode;
  cell: (row: T, index: number) => ReactNode;
  /** Providing this makes the column sortable. */
  sortValue?: (row: T) => SortValue;
  align?: "left" | "right" | "center";
  width?: string;
  /** Rendered as the card heading in the phone layout. */
  primary?: boolean;
  /** Left out of the phone card layout entirely. */
  hideOnMobile?: boolean;
};

export type RowTone = "muted" | "marker" | "highlight";

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: readonly T[];
  getRowId: (row: T) => string;
  /** Accessible table name. */
  caption: string;
  onRowClick?: (row: T) => void;
  selectedRowId?: string | null;
  rowTone?: (row: T) => RowTone | undefined;
  highlightedColumnId?: string | null;
  initialSort?: { columnId: string; direction: SortDirection } | null;
  empty?: ReactNode;
  /** Force a layout instead of switching to cards on phones. */
  layout?: "auto" | "table" | "cards";
  dense?: boolean;
};

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  caption,
  onRowClick,
  selectedRowId,
  rowTone,
  highlightedColumnId,
  initialSort = null,
  empty,
  layout = "auto",
  dense = false,
}: DataTableProps<T>) {
  const [sort, setSort] = useState(initialSort);
  const isPhone = useMediaQuery(PHONE_QUERY);
  const useCards = layout === "cards" || (layout === "auto" && isPhone);

  const sortedRows = useMemo(() => {
    const column = sort && columns.find((c) => c.id === sort.columnId);
    if (!sort || !column?.sortValue) return rows;
    return sortRows(rows, column.sortValue, sort.direction);
  }, [rows, columns, sort]);

  if (rows.length === 0 && empty != null) return <>{empty}</>;

  const rowClass = (row: T) =>
    [
      "data-table__row",
      onRowClick && "data-table__row--clickable",
      selectedRowId != null && getRowId(row) === selectedRowId && "data-table__row--selected",
      rowTone?.(row) && `data-table__row--${rowTone(row)}`,
    ]
      .filter(Boolean)
      .join(" ");

  const onRowKeyDown = (row: T) => (event: KeyboardEvent) => {
    if (onRowClick && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      onRowClick(row);
    }
  };

  if (useCards) {
    const primary = columns.find((c) => c.primary) ?? columns[0];
    const rest = columns.filter((c) => c !== primary && !c.hideOnMobile);
    return (
      <ul className="data-cards" aria-label={caption}>
        {sortedRows.map((row, index) => (
          <li
            key={getRowId(row)}
            className={rowClass(row)}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            onKeyDown={onRowKeyDown(row)}
            tabIndex={onRowClick ? 0 : undefined}
          >
            <div className="data-cards__primary">{primary.cell(row, index)}</div>
            <dl className="data-cards__fields">
              {rest.map((column) => (
                <div
                  key={column.id}
                  className={
                    column.id === highlightedColumnId ? "data-cards__field data-cards__field--highlight" : "data-cards__field"
                  }
                >
                  <dt>{column.header}</dt>
                  <dd>{column.cell(row, index)}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className={dense ? "data-table data-table--dense" : "data-table"}>
      <table>
        <caption className="data-table__caption">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => {
              const sorted = sort?.columnId === column.id ? sort.direction : null;
              const classes = [
                `data-table__cell--${column.align ?? "left"}`,
                column.id === highlightedColumnId && "data-table__col--highlight",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <th
                  key={column.id}
                  scope="col"
                  className={classes}
                  style={column.width ? { width: column.width } : undefined}
                  aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
                >
                  {column.sortValue ? (
                    <button
                      type="button"
                      className="data-table__sort"
                      onClick={() => setSort((current) => nextSort(current, column.id))}
                    >
                      {column.header}
                      {sorted === "asc" ? (
                        <ArrowUp aria-hidden />
                      ) : sorted === "desc" ? (
                        <ArrowDown aria-hidden />
                      ) : (
                        <ChevronsUpDown aria-hidden className="data-table__sort-idle" />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, index) => (
            <tr
              key={getRowId(row)}
              className={rowClass(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowKeyDown(row)}
              tabIndex={onRowClick ? 0 : undefined}
              aria-selected={selectedRowId != null ? getRowId(row) === selectedRowId : undefined}
            >
              {columns.map((column) => (
                <td
                  key={column.id}
                  className={[
                    `data-table__cell--${column.align ?? "left"}`,
                    column.id === highlightedColumnId && "data-table__col--highlight",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {column.cell(row, index)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
