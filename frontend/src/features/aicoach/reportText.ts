/** The first line of a report, without Markdown marks: what a card or a notification shows. */
export function headline(content: string): string {
  for (const raw of content.split("\n")) {
    const line = raw.trim().replace(/^[#>*\-\s]+/, "").replace(/[*_`]/g, "").trim();
    if (line) return line.length > 140 ? `${line.slice(0, 139)}…` : line;
  }
  return "";
}
