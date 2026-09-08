import { HORIZON_LABEL, Horizon, Prediction } from "@/lib/types";
import { pct, shortDate, usd } from "@/lib/format";

/**
 * Split probability bar.
 *
 * Both sides are always drawn, so the reader sees a *split* rather than a
 * single fill they might misread as a magnitude. The dominant side carries full
 * colour and the other is dimmed, which makes the call legible at a glance
 * without hiding the opposing probability.
 */
function ProbabilityBar({ pUp, pDown }: { pUp: number; pDown: number }) {
  const total = pUp + pDown || 1;
  const upPct = (pUp / total) * 100;
  const upLeads = pUp >= pDown;

  return (
    <div>
      <div
        className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-base"
        role="img"
        aria-label={`Probability up ${pct(pUp)}, down ${pct(pDown)}`}
      >
        <div
          className={`h-full rounded-l-full transition-[width,opacity] duration-500 ease-out ${
            upLeads ? "bg-up" : "bg-up/35"
          }`}
          style={{ width: `${upPct}%` }}
        />
        <div
          className={`h-full flex-1 rounded-r-full transition-opacity duration-500 ${
            upLeads ? "bg-down/35" : "bg-down"
          }`}
        />
      </div>
      <div className="mt-2 flex justify-between text-[11px] font-medium tnum">
        <span className={upLeads ? "text-up" : "text-ink-faint"}>Up {pct(pUp)}</span>
        <span className={upLeads ? "text-ink-faint" : "text-down"}>Down {pct(pDown)}</span>
      </div>
    </div>
  );
}

export function HorizonCard({
  horizon,
  prediction,
}: {
  horizon: Horizon;
  prediction?: Prediction;
}) {
  if (!prediction) {
    return (
      <div className="card flex min-h-[15rem] flex-col justify-between p-5">
        <h3 className="text-sm font-semibold text-ink-muted">{HORIZON_LABEL[horizon]}</h3>
        <p className="text-sm text-ink-faint">
          No prediction yet. Run the daily job to generate one.
        </p>
      </div>
    );
  }

  const isUp = prediction.pred_class === 1;
  const tone = isUp
    ? {
        text: "text-up",
        chip: "bg-up-soft text-up border-up/40",
        rule: "from-up/80",
        glow: "group-hover:shadow-[0_10px_34px_-18px_var(--color-up)]",
      }
    : {
        text: "text-down",
        chip: "bg-down-soft text-down border-down/40",
        rule: "from-down/80",
        glow: "group-hover:shadow-[0_10px_34px_-18px_var(--color-down)]",
      };

  return (
    <article
      className={`card group relative overflow-hidden p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-ink-faint/40 ${tone.glow}`}
    >
      {/* Direction rule, fading out to the right so it reads as an accent
          rather than a second border. */}
      <div
        aria-hidden
        className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r to-transparent ${tone.rule}`}
      />

      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">{HORIZON_LABEL[horizon]}</h3>
          <p className="mt-0.5 text-[11px] text-ink-faint">
            Resolves {shortDate(prediction.target_date)}
          </p>
        </div>
        <span
          className={`rounded-md border px-2.5 py-1 text-[11px] font-bold tracking-wider ${tone.chip}`}
        >
          {isUp ? "UP" : "DOWN"}
        </span>
      </header>

      <div className="mt-6 flex items-baseline gap-2">
        <span className={`text-[2.75rem] font-semibold leading-none tnum ${tone.text}`}>
          {pct(prediction.confidence, 0)}
        </span>
        <span className="text-[11px] font-medium uppercase tracking-widest text-ink-faint">
          confidence
        </span>
      </div>

      <div className="mt-5">
        <ProbabilityBar pUp={prediction.p_up} pDown={prediction.p_down} />
      </div>

      <footer className="mt-5 flex items-center justify-between border-t border-line pt-3 text-[11px] text-ink-faint">
        <span>From {shortDate(prediction.as_of_date)} close</span>
        <span className="tnum text-ink-muted">{usd(prediction.as_of_close)}</span>
      </footer>
    </article>
  );
}
