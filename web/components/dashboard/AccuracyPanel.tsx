import { Accuracy, HORIZON_LABEL } from "@/lib/types";
import { pct } from "@/lib/format";

/**
 * Independent events required before this panel will call a horizon skilled or
 * unskilled. Below it, the honest answer is "not enough evidence yet".
 */
const MIN_EVENTS_FOR_VERDICT = 30;

/**
 * Balanced accuracy is the headline, not the plain hit rate.
 *
 * These indices close up on ~55% of days and ~68% of 20-day windows. A model
 * that simply always said UP would post a hit rate near those numbers while
 * knowing nothing -- an earlier version of this project did exactly that, and
 * the hit rate hid it completely. Balanced accuracy is the mean of per-class
 * recall, so an always-UP model scores 0.50 no matter what. Anything above 0.50
 * is genuine separation of up-days from down-days.
 */
export function AccuracyPanel({ rows }: { rows: Accuracy[] }) {
  return (
    <section className="card p-5" aria-labelledby="track-record">
      <header className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="track-record" className="text-sm font-semibold text-ink">
          Track record
        </h2>
        <p className="text-[11px] text-ink-faint">
          Resolved predictions only, most recent 200 per horizon
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        {rows.map((r) => {
          const bal = r.balancedAccuracy;
          const skill = bal === null ? null : bal - 0.5;
          const events = r.effectiveEvents ?? 0;

          // A verdict needs enough INDEPENDENT events to mean anything. Twenty
          // 20-day calls overlap into ~1 outcome, so a "has signal" badge off a
          // handful of them would be noise dressed as a finding.
          const enough = events >= MIN_EVENTS_FOR_VERDICT;
          const verdict = !enough
            ? { text: "too few events", tone: "bg-surface text-ink-faint",
                why: `Only ~${events} independent events; needs ${MIN_EVENTS_FOR_VERDICT} before a verdict means anything` }
            : skill !== null && skill > 0.01
              ? { text: "has signal", tone: "bg-up-soft text-up",
                  why: "Balanced accuracy is above 50%: the model separates up from down" }
              : { text: "no signal", tone: "bg-surface text-ink-faint",
                  why: "Balanced accuracy is at or below 50%: no measurable skill" };

          return (
            <div key={r.horizon} className="rounded-lg border border-line bg-surface-2 p-4">
              <div className="flex items-baseline justify-between">
                <p className="text-[11px] font-medium uppercase tracking-wider text-ink-faint">
                  {HORIZON_LABEL[r.horizon]}
                </p>
                {skill !== null && (
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${verdict.tone}`}
                    title={verdict.why}
                  >
                    {verdict.text}
                  </span>
                )}
              </div>

              {r.resolved === 0 ? (
                <p className="mt-3 text-sm text-ink-faint">Not enough resolved data</p>
              ) : (
                <>
                  <p
                    className={`mt-1.5 text-3xl font-semibold tnum ${
                      enough && skill !== null && skill > 0.01 ? "text-ink" : "text-ink-muted"
                    }`}
                  >
                    {pct(bal, 1)}
                  </p>
                  <p className="mt-1 text-[11px] text-ink-faint">
                    balanced accuracy · 50% = no skill
                  </p>
                  <p
                    className="mt-1 text-[11px] text-ink-faint"
                    title="Overlapping windows and four correlated ETFs mean the raw count of resolved predictions overstates the sample"
                  >
                    ~{r.effectiveEvents ?? "—"} independent events
                  </p>

                  <dl className="mt-3 space-y-1 border-t border-line pt-2.5 text-[11px]">
                    <div className="flex justify-between">
                      <dt className="text-ink-faint">Plain hit rate</dt>
                      <dd className="tnum text-ink-muted">
                        {pct(r.accuracy, 1)}{" "}
                        <span className="text-ink-faint">
                          ({r.hits}/{r.resolved})
                        </span>
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-ink-faint">Market rose</dt>
                      <dd className="tnum text-ink-muted">{pct(r.baseline, 1)}</dd>
                    </div>
                    <div className="flex justify-between">
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
        Plain hit rate is misleading on its own: the market rises far more often than it
        falls, so always predicting UP would score near the &ldquo;market rose&rdquo; figure
        while carrying no information. Balanced accuracy weights up-days and down-days
        equally, so only a model that reads both can beat 50%. Each horizon is scored
        separately, against its own base rate. Note the independent-event counts: a
        20-day call overlaps the previous nineteen, so a long run of resolved predictions
        is far less evidence than it looks.
      </p>
    </section>
  );
}
