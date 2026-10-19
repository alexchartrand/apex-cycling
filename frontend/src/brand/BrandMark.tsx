// Compact mark (velodrome oval + apex marker + Bebas "A"), used where the
// full wordmark doesn't fit: collapsed sidebar, mobile top bar. Same
// drawing as public/favicon.svg, but token-colored so it follows the theme.
export function BrandMark({ className, size = 32 }: { className?: string; size?: number }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="ApexCycling">
      <rect width="64" height="64" rx="14" style={{ fill: "var(--wordmark-ink)" }} />
      <rect x="8" y="17" width="48" height="30" rx="15" fill="none" stroke="#C9A673" strokeWidth="7" />
      <rect x="8" y="17" width="48" height="30" rx="15" fill="none" stroke="var(--color-accent)" strokeWidth="1.5" />
      <line x1="49" y1="32" x2="60" y2="32" stroke="var(--color-marker)" strokeWidth="3" strokeLinecap="round" />
      <g style={{ fill: "var(--color-bg)" }} transform="translate(26.6,41) scale(0.0257,-0.0257)">
        <path d="M126 700H275L389 0H279L259 139V137H134L114 0H12ZM246 232 197 578H195L147 232Z" />
      </g>
    </svg>
  );
}
