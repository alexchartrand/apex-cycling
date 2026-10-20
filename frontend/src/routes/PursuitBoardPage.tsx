import { useEffect, useReducer, useState } from "react";
import { ChevronLeft, RotateCcw, Undo2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";
import { Button } from "../components/ui";
import { useFormat } from "../i18n/useFormat";
import { boardReducer, INITIAL_BOARD, paceOf, tapDeltas } from "../features/tools/pursuitBoard";
import { usePursuitSchedule } from "../features/tools/usePursuitSchedule";
import { useToolInputs } from "../features/tools/useToolInputs";
import "./PursuitBoardPage.css";

/**
 * Full-screen, large-type pursuit board for the coach at the track side:
 * start the clock at the gun, tap at every pursuit line, and read the gap to
 * the schedule from across the infield.
 */
export function PursuitBoardPage() {
  const { t } = useTranslation("tools");
  const fmt = useFormat();
  const { search } = useLocation();
  const inputs = useToolInputs();
  const result = usePursuitSchedule(inputs);
  const [state, dispatch] = useReducer(boardReducer, INITIAL_BOARD);
  const [now, setNow] = useState(() => Date.now());

  const rows = result.kind === "ok" ? result.schedule.rows : [];
  const scheduled = rows.map((row) => row.elapsedS);
  const deltas = tapDeltas(state, scheduled);
  const finished = rows.length > 0 && state.taps.length >= rows.length;
  const running = state.startedAt !== null && !finished;
  const next = rows[state.taps.length];
  const lastDelta = deltas.at(-1);
  const elapsedMs =
    state.startedAt === null ? 0 : (finished ? state.taps[rows.length - 1] : now) - state.startedAt;

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(Date.now()), 50);
    return () => window.clearInterval(id);
  }, [running]);

  // Keep the screen on while timing (where the browser supports it).
  useEffect(() => {
    if (!running || !("wakeLock" in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    navigator.wakeLock.request("screen").then(
      (sentinel) => (lock = sentinel),
      () => {},
    );
    return () => void lock?.release();
  }, [running]);

  const press = () => dispatch(state.startedAt === null ? { type: "start", at: Date.now() } : { type: "tap", at: Date.now() });

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLElement && event.target.closest("a, button")) return;
      if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        if (!finished) dispatch(state.startedAt === null ? { type: "start", at: Date.now() } : { type: "tap", at: Date.now() });
      } else if (event.key === "Backspace") {
        dispatch({ type: "undo" });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.startedAt, finished]);

  const plannerSearch = search;
  const paceLabel = lastDelta === undefined ? null : paceOf(lastDelta);

  return (
    <div className="board">
      <header className="board__bar">
        <Link to={`/tools/pursuit${plannerSearch}`} className="board__exit">
          <ChevronLeft aria-hidden />
          {t("board.exit")}
        </Link>
        <div className="board__bar-actions">
          <Button variant="ghost" size="sm" icon={<Undo2 aria-hidden />} onClick={() => dispatch({ type: "undo" })} disabled={state.taps.length === 0}>
            {t("board.undo")}
          </Button>
          <Button variant="ghost" size="sm" icon={<RotateCcw aria-hidden />} onClick={() => dispatch({ type: "reset" })} disabled={state.startedAt === null}>
            {t("board.reset")}
          </Button>
        </div>
      </header>

      {result.kind !== "ok" ? (
        <p className="board__message">{t(result.kind === "invalid" ? "results.invalid" : "results.unreachable")}</p>
      ) : (
        <>
          <div className="board__clock" aria-live="off">
            {fmt.lapTime(elapsedMs).slice(0, -2)}
          </div>

          <div className="board__panels">
            <section className="board__panel">
              <h2 className="board__label">
                {finished ? t("board.done") : next ? t("board.halfLapOf", { n: next.halfLap, total: rows.length }) : null}
              </h2>
              <div className="board__target">
                {finished ? fmt.lapTime(scheduled.at(-1)! * 1000) : next && fmt.lapTime(next.elapsedS * 1000).slice(0, -1)}
              </div>
              {next?.lapS != null && !finished && (
                <div className="board__sub">
                  {t("pursuit.lapTime")} {fmt.seconds(next.lapS * 1000, 2)}
                </div>
              )}
            </section>
            <section className={`board__panel board__panel--gap${paceLabel ? ` board__panel--${paceLabel}` : ""}`} aria-live="polite">
              <h2 className="board__label">{t("board.lastGap")}</h2>
              <div className="board__target">{lastDelta === undefined ? "—" : fmt.deltaSeconds(lastDelta * 1000, 2)}</div>
              {paceLabel && <div className="board__sub">{t(`board.${paceLabel}`)}</div>}
            </section>
          </div>

          <button type="button" className="board__tap" onClick={press} disabled={finished}>
            {state.startedAt === null ? t("board.start") : t("board.tap")}
          </button>
          <p className="board__hint">{state.startedAt === null ? t("board.startHint") : t("board.keys")}</p>

          <ol className="board__rows">
            {rows.map((row, i) => (
              <li
                key={row.halfLap}
                className={[
                  "board__row",
                  row.lap === null && "board__row--half",
                  i === state.taps.length && !finished && "board__row--next",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span>{row.lap ?? "½"}</span>
                <span>{fmt.lapTime(row.elapsedS * 1000)}</span>
                <span className={deltas[i] === undefined ? "" : `board__delta board__delta--${paceOf(deltas[i])}`}>
                  {deltas[i] === undefined ? "" : fmt.deltaSeconds(deltas[i] * 1000, 2)}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
