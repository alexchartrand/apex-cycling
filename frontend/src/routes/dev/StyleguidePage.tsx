import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Bike,
  CalendarDays,
  CircleGauge,
  Flag,
  Gauge,
  Home,
  ListOrdered,
  Medal,
  Monitor,
  Moon,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Sun,
  Timer,
  Trophy,
  Wrench,
  Zap,
} from "lucide-react";
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BrandMark } from "../../brand/BrandMark";
import { Wordmark } from "../../brand/Wordmark";
import { Badge, Button, Card, IconButton, SegmentedControl, StatTile } from "../../components/ui";
import { formatMs } from "../../features/training/format";
import type { ThemeMode } from "../../theme/theme";
import { useTheme } from "../../theme/useTheme";
import "./StyleguidePage.css";

/*
  Dev-only living style guide (mounted only when import.meta.env.DEV, see
  App.tsx). The "Home preview" section is static mock data used to review
  the design direction before it's rolled out to real screens.
*/

const THEME_OPTIONS = [
  { value: "system" as const, label: "System", icon: <Monitor aria-hidden /> },
  { value: "light" as const, label: "Paper", icon: <Sun aria-hidden /> },
  { value: "dark" as const, label: "Night", icon: <Moon aria-hidden /> },
];

const SEMANTIC_COLORS = [
  ["--color-bg", "Background"],
  ["--color-surface", "Surface"],
  ["--color-surface-2", "Surface 2"],
  ["--color-surface-sunken", "Sunken"],
  ["--color-border", "Border"],
  ["--color-text", "Text"],
  ["--color-text-2", "Text 2"],
  ["--color-accent", "Accent"],
  ["--color-marker", "Marker (PR)"],
  ["--color-highlight", "Highlight"],
  ["--color-positive", "Faster"],
  ["--color-negative", "Slower"],
];

const CHART_COLORS = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5", "--chart-6"];

// 24 laps of a plausible flying-effort session on a 250 m track.
const MOCK_LAPS = [
  19.42, 18.91, 18.6, 18.44, 18.71, 19.88, 21.4, 22.1, 18.32, 18.05, 17.9, 18.12, 19.6, 22.8, 23.1, 18.4, 18.22,
  18.31, 18.55, 18.9, 20.4, 22.6, 19.1, 18.8,
].map((s, i) => ({ lap: i + 1, ms: Math.round(s * 1000) }));

const MOCK_FORM = Array.from({ length: 42 }, (_, i) => {
  const fitness = 42 + i * 0.35 + Math.sin(i / 4) * 2;
  const fatigue = fitness + Math.sin(i / 2.2) * 9 + 2;
  return { day: i, fitness: +fitness.toFixed(1), fatigue: +fatigue.toFixed(1), form: +(fitness - fatigue).toFixed(1) };
});

const MOCK_RECORDS = [
  { event: "Flying 200 m", time: "11.482", date: "Oct 17", isNew: true },
  { event: "Flying lap", time: "17.900", date: "Oct 17", isNew: true },
  { event: "500 m standing", time: "35.210", date: "Sep 28", isNew: false },
  { event: "Kilo", time: "1:08.441", date: "Sep 28", isNew: false },
  { event: "4 km pursuit", time: "4:42.870", date: "Aug 30", isNew: false },
];

export function StyleguidePage() {
  const { mode, setMode, resolved } = useTheme();

  return (
    <div className="sg">
      <header className="sg__top">
        <Wordmark className="sg__wordmark" />
        <div className="sg__top-meta">
          <span className="eyebrow">Design system · {resolved === "dark" ? "Night session" : "Paper"}</span>
          <SegmentedControl<ThemeMode> aria-label="Theme" options={THEME_OPTIONS} value={mode} onChange={setMode} />
        </div>
      </header>

      <Section title="Home preview" note="Static mock data — how the reworked app is meant to feel.">
        <PreviewShell>
          <HomePreview />
        </PreviewShell>
      </Section>

      <Section title="Color" note="Semantic tokens; every component uses these, never raw brand values.">
        <div className="sg__swatches">
          {SEMANTIC_COLORS.map(([token, label]) => (
            <Swatch key={token} token={token} label={label} />
          ))}
        </div>
        <div className="sg__swatches sg__swatches--chart">
          {CHART_COLORS.map((token, i) => (
            <Swatch key={token} token={token} label={`Series ${i + 1}`} />
          ))}
        </div>
      </Section>

      <Section title="Type" note="Barlow Condensed for headlines & numbers, Inter for UI, IBM Plex Mono for labels.">
        <div className="sg__type">
          <span className="eyebrow">Eyebrow · IBM Plex Mono</span>
          <h1>Session quotidienne — Bromont</h1>
          <h2>Personal records</h2>
          <h3>Flying 200 m</h3>
          <p>
            Body text in Inter. Tabular figures keep lap times aligned: <span className="num">0:11.482</span> /{" "}
            <span className="num">0:17.903</span> / <span className="num">1:08.441</span>.
          </p>
          <p className="sg__muted">Secondary text for hints and metadata.</p>
          <div className="sg__bigtime">{formatMs(11_482)}</div>
        </div>
      </Section>

      <Section title="Buttons & badges">
        <div className="sg__row">
          <Button icon={<Plus aria-hidden />}>Import session</Button>
          <Button variant="secondary">Compare</Button>
          <Button variant="ghost">Cancel</Button>
          <Button variant="danger">Delete</Button>
          <Button loading>Syncing</Button>
          <Button size="sm" variant="secondary" icon={<RefreshCw aria-hidden />}>
            Sync
          </Button>
          <IconButton aria-label="Settings" variant="secondary">
            <Wrench aria-hidden />
          </IconButton>
        </div>
        <div className="sg__row">
          <Badge tone="marker" icon={<Trophy aria-hidden />}>
            PR
          </Badge>
          <Badge tone="positive">−0.214 s</Badge>
          <Badge tone="negative">+0.380 s</Badge>
          <Badge tone="accent">Flying</Badge>
          <Badge tone="highlight">Standing start</Badge>
          <Badge>Excluded</Badge>
        </div>
      </Section>

      <Section title="Stat tiles">
        <div className="sg__tiles">
          <StatTile
            label="Best flying 200"
            icon={<Timer aria-hidden />}
            value="11.482"
            unit="s"
            tone="marker"
            delta={{ label: "0.214 s", direction: "better" }}
            hint="vs previous best"
          />
          <StatTile label="Top speed" icon={<Gauge aria-hidden />} value="62.7" unit="km/h" tone="accent" />
          <StatTile
            label="Avg lap (efforts)"
            icon={<CircleGauge aria-hidden />}
            value="18.42"
            unit="s"
            delta={{ label: "0.12 s", direction: "worse" }}
          />
          <StatTile label="Laps" icon={<ListOrdered aria-hidden />} value="142" hint="35.5 km" />
        </div>
      </Section>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="sg__section">
      <div className="sg__section-head">
        <h2>{title}</h2>
        {note && <p className="sg__muted">{note}</p>}
      </div>
      {children}
    </section>
  );
}

function Swatch({ token, label }: { token: string; label: string }) {
  return (
    <div className="sg__swatch">
      <div className="sg__swatch-chip" style={{ background: `var(${token})` }} />
      <div className="sg__swatch-label">{label}</div>
      <code className="sg__swatch-token">{token}</code>
    </div>
  );
}

const PREVIEW_NAV = [
  { icon: Home, label: "Home", active: true },
  { icon: CalendarDays, label: "Log" },
  { icon: Trophy, label: "Records" },
  { icon: BarChart3, label: "Progress" },
  { icon: Wrench, label: "Tools" },
  { icon: Zap, label: "Aero lab" },
  { icon: Bike, label: "Equipment" },
];

const PREVIEW_TABS = [
  { icon: Home, label: "Home", active: true },
  { icon: CalendarDays, label: "Log" },
  { icon: Trophy, label: "Records" },
  { icon: Wrench, label: "Tools" },
  { icon: MoreHorizontal, label: "More" },
];

function PreviewShell({ children }: { children: ReactNode }) {
  return (
    <div className="pv-shell">
      <aside className="pv-shell__sidebar">
        <Wordmark className="pv-shell__wordmark" />
        <nav className="pv-shell__nav">
          {PREVIEW_NAV.map(({ icon: Icon, label, active }) => (
            <span key={label} className={active ? "pv-shell__link pv-shell__link--active" : "pv-shell__link"}>
              <Icon aria-hidden />
              {label}
            </span>
          ))}
        </nav>
        <div className="pv-shell__athlete">
          <span className="pv-shell__avatar">CL</span>
          <div>
            <div className="pv-shell__athlete-name">Camille Lavoie</div>
            <div className="pv-shell__athlete-club">CNCB · Junior</div>
          </div>
        </div>
      </aside>
      <div className="pv-shell__main">
        <div className="pv-shell__topbar">
          <BrandMark size={30} />
          <span className="pv-shell__topbar-title">Home</span>
          <span className="pv-shell__avatar pv-shell__avatar--sm">CL</span>
        </div>
        <div className="pv-shell__content">{children}</div>
        <nav className="pv-shell__tabbar">
          {PREVIEW_TABS.map(({ icon: Icon, label, active }) => (
            <span key={label} className={active ? "pv-shell__tab pv-shell__tab--active" : "pv-shell__tab"}>
              <Icon aria-hidden />
              {label}
            </span>
          ))}
        </nav>
      </div>
    </div>
  );
}

function HomePreview() {
  const bestLap = Math.min(...MOCK_LAPS.map((l) => l.ms));
  return (
    <div className="pv-home">
      <div className="pv-home__hero">
        <div>
          <span className="eyebrow">Tuesday, October 19</span>
          <h1 className="pv-home__greeting">Good evening, Camille</h1>
        </div>
        <div className="pv-home__hero-actions">
          <Badge tone="positive" icon={<RefreshCw aria-hidden />}>
            Sqorz synced 12 min ago
          </Badge>
          <Button size="sm" icon={<Plus aria-hidden />}>
            Import
          </Button>
        </div>
      </div>

      <div className="pv-home__week">
        <StatTile label="Sessions this week" value="3" delta={{ label: "1", direction: "better" }} hint="vs last week" />
        <StatTile label="Laps" value="142" hint="35.5 km on track" />
        <StatTile label="Track time" value="2:40" unit="h" />
        <StatTile label="Form" value="+6" tone="highlight" hint="Fresh — good day to go fast" />
      </div>

      <div className="pv-home__grid">
        <div className="pv-home__col">
          <Card
            className="pv-home__latest"
            eyebrow="Latest session · Sun Oct 17 · Bromont"
            title="Session quotidienne"
            actions={
              <Button size="sm" variant="secondary">
                Open
              </Button>
            }
          >
            <div className="pv-home__latest-stats">
              <StatTile
                label="Flying 200"
                icon={<Flag aria-hidden />}
                value="11.482"
                unit="s"
                tone="marker"
                delta={{ label: "0.214 s · PR", direction: "better" }}
              />
              <StatTile label="Best lap" icon={<Timer aria-hidden />} value={(bestLap / 1000).toFixed(3)} unit="s" />
              <StatTile label="Top speed" icon={<Gauge aria-hidden />} value="62.7" unit="km/h" />
            </div>
            <div className="pv-home__chart">
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={MOCK_LAPS} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                  <XAxis
                    dataKey="lap"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
                  />
                  <YAxis
                    reversed
                    domain={["dataMin - 400", "dataMax + 400"]}
                    tickFormatter={(ms: number) => (ms / 1000).toFixed(1)}
                    tickLine={false}
                    axisLine={false}
                    width={36}
                    tick={{ fill: "var(--chart-axis)", fontSize: 12 }}
                  />
                  <Tooltip
                    cursor={{ stroke: "var(--color-border-strong)" }}
                    contentStyle={{
                      background: "var(--color-surface)",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      color: "var(--color-text)",
                    }}
                    formatter={(value) => [formatMs(Number(value)), "Lap"]}
                    labelFormatter={(lap) => `Lap ${lap}`}
                  />
                  <Area
                    type="monotone"
                    dataKey="ms"
                    stroke="var(--chart-1)"
                    strokeWidth={2}
                    fill="var(--chart-1)"
                    fillOpacity={0.1}
                    baseValue="dataMax"
                    dot={false}
                    activeDot={{ r: 4, fill: "var(--chart-1)" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
              <p className="pv-home__chart-note">Lap times — faster is up</p>
            </div>
          </Card>
          <Card eyebrow="Goal · Nov 23 · Championnats québécois" title="4 km pursuit in 4:35.000">
            <div className="pv-goal">
              <div className="pv-goal__bar">
                <div className="pv-goal__fill" style={{ width: "72%" }} />
              </div>
              <div className="pv-goal__meta">
                <span>
                  Current best <strong className="num">4:42.870</strong>
                </span>
                <span>
                  Predicted <strong className="num">4:38.2</strong>
                </span>
              </div>
            </div>
          </Card>
        </div>

        <div className="pv-home__col">
          <Card eyebrow="All tracks" title="Personal records" actions={<Medal className="pv-home__card-icon" aria-hidden />}>
            <ul className="pv-records">
              {MOCK_RECORDS.map((record) => (
                <li key={record.event} className="pv-records__row">
                  <span className="pv-records__event">{record.event}</span>
                  {record.isNew && (
                    <Badge tone="marker" icon={<Trophy aria-hidden />}>
                      New
                    </Badge>
                  )}
                  <span className="pv-records__time">{record.time}</span>
                  <span className="pv-records__date">{record.date}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card eyebrow="Last 6 weeks" title="Fitness & form" actions={<Activity className="pv-home__card-icon" aria-hidden />}>
            <ResponsiveContainer width="100%" height={150}>
              <LineChart data={MOCK_FORM} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                <XAxis dataKey="day" hide />
                <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--chart-axis)", fontSize: 11 }} />
                <Line type="monotone" dataKey="fitness" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="fatigue" stroke="var(--chart-2)" strokeWidth={1.5} dot={false} strokeOpacity={0.7} />
                <Line type="monotone" dataKey="form" stroke="var(--chart-3)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div className="pv-legend">
              <span style={{ ["--dot" as string]: "var(--chart-1)" }}>Fitness</span>
              <span style={{ ["--dot" as string]: "var(--chart-2)" }}>Fatigue</span>
              <span style={{ ["--dot" as string]: "var(--chart-3)" }}>Form</span>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
