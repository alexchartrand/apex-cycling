import "./Skeleton.css";

/** Shimmering placeholder sized like the content it stands in for. */
export function Skeleton({
  width = "100%",
  height = 16,
  radius = "var(--radius-sm)",
  className,
}: {
  width?: number | string;
  height?: number | string;
  radius?: string;
  className?: string;
}) {
  return (
    <span
      className={["skeleton", className].filter(Boolean).join(" ")}
      style={{ width, height, borderRadius: radius }}
      aria-hidden
    />
  );
}

/** A loading block for a whole region; announces "Loading…" once. */
export function SkeletonGroup({ lines = 3, label = "Loading…" }: { lines?: number; label?: string }) {
  return (
    <div className="skeleton-group" role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}
