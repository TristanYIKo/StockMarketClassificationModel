import { Accuracy, HORIZON_LABEL } from "@/lib/types";
import { pct, shortDate } from "@/lib/format";
import { VerdictBadge } from "@/components/dashboard/VerdictBadge";

/** Shared scale for every interval strip, so the three horizons compare by eye. */
const LO = 0.3;
const HI = 0.7;
const pos = (v: number) => `${((Math.min(HI, Math.max(LO, v)) - LO) / (HI - LO)) * 100}%`;

/**
 * Point estimate and 95% range against the 50% line.
 *
 * The number alone invites "52.8% > 50%, so it works". The strip shows the
 * honest version: how wide the range is and whether it clears chance.
 */
function IntervalStrip({ value, ci, tone }: { value: number; ci: number; tone: string }) {
  const lo = value - ci;
  const hi = value + ci;
  return (
    <div className="mt-4" role="img"
      aria-label={`Balanced accuracy ${pct(value, 1)}, 95% range ${pct(lo, 1)} to ${pct(hi, 1)}; chance is 50%`}>
      <div className="relative h-4">
        {/* track */}
        <div aria-hidden className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-line" />
        {/* chance line */}
        <div aria-hidden className="absolute top-0 bottom-0 w-px bg-ink-faint" style={{ left: pos(0.5) }} />
        {/* 95% range */}
        <div
          aria-hidden
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-ink-faint/45"
          style={{ left: pos(lo), right: `calc(100% - ${pos(hi)})` }}
        />
        {/* estimate: >=8px marker with a 2px surface ring */}
        <div
          aria-hidden
          className={`absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface-2 ${tone}`}
          style={{ left: pos(value) }}
        />
      </div>
      <div aria-hidden className="relative mt-1 h-3 text-[10px] text-ink-faint">
        <span className="absolute left-0">{pct(LO, 0)}</span>
        <span className="absolute -translate-x-1/2" style={{ left: pos(0.5) }}>50% chance</span>
        <span className="absolute right-0">{pct(HI, 0)}</span>
      </div>
    </div>
  );
}

/**
 * Balanced accuracy is the headline, not the plain hit rate.
 *
 * These indices close up on ~55% of days and ~65% of 20-day windows. A model
 * that always said UP would post a hit rate near those numbers while knowing
 * nothing -- an earlier version of this project did exactly that. Balanced
 * accuracy is the mean of per-class recall, so always-UP scores 0.50 no matter
 * what. The verdict comes from the 95% range, not from the estimate clearing
 * 50% by a hair.
 */
export function AccuracyPanel({ rows }: { rows: Accuracy[] }) {
  const first = rows.map((r) => r.firstDate).filter(Boolean).sort()[0];
  const last = rows.map((r) => r.lastDate).filter(Boolean).sort().at(-1);

  return (
    <section className="card p-5" aria-labelledby="track-record">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="track-record" className="text-sm font-semibold text-ink">
            Track record
          </h2>
          <p className="mt-0.5 text-[11px] text-ink-faint">
            Every resolved call
            {first && last ? ` from ${shortDate(first)} to ${shortDate(last)}` : ""}, scored
            against its own outcome
          </p>
        </div>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        {rows.map((r) => {
          const bal = r.balancedAccuracy;
          const tone =
            r.verdict === "beats-chance" ? "bg-up" : r.verdict === "worse" ? "bg-down" : "bg-ink";

          return (
            <div key={r.horizon} className="rounded-lg border border-line bg-surface-2 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-ink-faint">
                  {HORIZON_LABEL[r.horizon]}
                </p>
                <VerdictBadge verdict={r.verdict} size="xs" />
              </div>

              {r.resolved === 0 || bal === null ? (
                <p className="mt-3 text-sm text-ink-faint">No resolved calls yet</p>
              ) : (
                <>
                  <p className="mt-2 text-3xl font-semibold text-ink">{pct(bal, 1)}</p>
                  <p className="mt-1 text-[11px] text-ink-faint">
                    balanced accuracy
                    {r.ci95 !== null && (
                      <>
                        {" "}· <span className="tnum">±{(r.ci95 * 100).toFixed(1)}</span> pts (95%)
                      </>
                    )}
                  </p>

                  {r.ci95 !== null && <IntervalStrip value={bal} ci={r.ci95} tone={tone} />}

                  <dl className="mt-4 space-y-1 border-t border-line pt-2.5 text-[11px]">
                    <div className="flex justify-between gap-3">
                      <dt className="text-ink-faint">Calls scored</dt>
                      <dd className="tnum text-ink-muted">{r.resolved}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt
                        className="text-ink-faint"
                        title="Overlapping windows mean the raw count of calls badly overstates the evidence"
                      >
                        Independent outcomes
                      </dt>
                      <dd className="tnum text-ink-muted">~{r.effectiveEvents}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt className="text-ink-faint">Plain hit rate</dt>
                      <dd className="tnum text-ink-muted">{pct(r.accuracy, 1)}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt className="text-ink-faint">Market rose</dt>
                      <dd className="tnum text-ink-muted">{pct(r.baseline, 1)}</dd>
                    </div>
                    <div className="flex justify-between gap-3">
                      <dt className="text-ink-faint">Called UP</dt>
                      <dd className="tnum text-ink-muted">{pct(r.upRate, 1)}</dd>
                    </div>
                  </dl>
                </>
              )}
            </div>
          );
        })}
      </div>

      <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-faint">
        <span className="font-medium text-ink-muted">Reading this.</span> Balanced accuracy
        averages how often the model was right on up-days and on down-days, so always
        saying UP scores exactly 50% however often the market rises. The grey band is the
        95% range around the estimate given how few independent outcomes there are; a
        horizon only gets &ldquo;beats chance&rdquo; when the whole band clears the 50%
        line. Consecutive 20-day calls share nineteen of their twenty days, so hundreds of
        calls can amount to a few dozen real outcomes.
      </p>
    </section>
  );
}
