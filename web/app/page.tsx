import { getDashboard, getQuotes } from "@/lib/data";
import { SYMBOLS, SYMBOL_NAME, HORIZONS, Symbol } from "@/lib/types";
import { shortDate, signedPct, usd } from "@/lib/format";
import { SymbolSwitcher } from "@/components/dashboard/SymbolSwitcher";
import { HorizonCard } from "@/components/dashboard/HorizonCard";
import { AccuracyPanel } from "@/components/dashboard/AccuracyPanel";
import { SignalChart } from "@/components/dashboard/SignalChart";
import { HistoryTable } from "@/components/dashboard/HistoryTable";

// Predictions change once a day, after the close, but a retrain can rewrite the
// whole history at any time. Ten minutes keeps the page cheap to serve while
// bounding how long a superseded model's calls can linger on screen.
export const revalidate = 600;

function isSymbol(v: string | undefined): v is Symbol {
  return !!v && (SYMBOLS as readonly string[]).includes(v);
}

function Notice({ title, body }: { title: string; body: React.ReactNode }) {
  return (
    <div className="card border-pending/30 bg-pending/5 p-5">
      <p className="text-sm font-semibold text-pending">{title}</p>
      {/* File paths and shell commands are long unbroken tokens; without an
          explicit break they push the whole page into horizontal scroll on
          narrow viewports. */}
      <div className="mt-1.5 [overflow-wrap:anywhere] text-sm text-ink-muted">{body}</div>
    </div>
  );
}

/**
 * How a call is produced, in three steps. The point a reader most needs and
 * cannot infer from the numbers: no call ever saw its own outcome.
 */
function MethodNote() {
  const steps = [
    {
      n: "1",
      title: "Only what was known that evening",
      body: "After each close, a fresh model is trained from scratch on past days whose outcome was already settled by then: everything up to one, five or twenty sessions earlier. Economic data counts from the day it is published, not the day it describes.",
    },
    {
      n: "2",
      title: "One model, one day",
      body: "That model makes the four calls for that day only, then is thrown away. Tomorrow's calls come from tomorrow's model, which has one more day of history.",
    },
    {
      n: "3",
      title: "History made the same way",
      body: "Every past call on this page was produced by that same day-by-day process, then scored against what the market actually did. Nothing here was fit to the outcomes it is graded on.",
    },
  ];
  return (
    <section className="card p-5" aria-labelledby="method-heading">
      <h2 id="method-heading" className="text-sm font-semibold text-ink">
        How each call is made
      </h2>
      <ol className="mt-4 grid gap-4 md:grid-cols-3">
        {steps.map((s) => (
          <li key={s.n} className="flex gap-3">
            <span
              aria-hidden
              className="flex size-6 shrink-0 items-center justify-center rounded-full border border-line text-[11px] font-semibold text-ink-muted"
            >
              {s.n}
            </span>
            <div>
              <p className="text-[13px] font-medium text-ink">{s.title}</p>
              <p className="mt-1 text-[12px] leading-relaxed text-ink-faint">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-faint">
        Inputs: price, volatility and volume patterns, rates and credit spreads, the Fed
        balance sheet, VIX, other asset classes, and FOMC/CPI/jobs-report dates. Which
        algorithm each horizon uses, and where its UP/DOWN line sits, was chosen on 2024
        data before any of the calls scored here.
      </p>
    </section>
  );
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ symbol?: string }>;
}) {
  const params = await searchParams;
  const symbol: Symbol = isSymbol(params.symbol) ? params.symbol : "SPY";
  const [data, quotes] = await Promise.all([getDashboard(symbol), getQuotes()]);
  const quote = quotes.find((q) => q.symbol === symbol);
  const accuracyFor = (h: (typeof HORIZONS)[number]) => data.accuracy.find((a) => a.horizon === h);

  return (
    <div className="min-h-screen">
      <div className="grid-veil border-b border-line/60">
        <div className="mx-auto max-w-6xl px-5 pt-8 pb-7 sm:px-8 sm:pt-10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-ink-faint">
              Market Direction Model
            </p>
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[11px] text-ink-muted">
              <span
                aria-hidden
                className="inline-block size-1.5 rounded-full bg-up shadow-[0_0_6px_var(--color-up)]"
              />
              Data through {shortDate(data.lastBarDate)}
            </span>
          </div>

          <div className="mt-5 flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
                {symbol}
                <span className="ml-3 text-lg font-normal text-ink-muted sm:text-xl">
                  {SYMBOL_NAME[symbol]}
                </span>
              </h1>
              <p className="mt-1.5 text-sm text-ink-faint">
                Will it close higher in 1, 5 and 20 trading days? One call per horizon, made
                after each close.
              </p>
            </div>

            {quote?.close != null && (
              <div className="text-left sm:text-right">
                <p className="text-3xl font-semibold tnum text-ink sm:text-4xl">
                  {usd(quote.close)}
                </p>
                {quote.changePct !== null && (
                  <p
                    className={`mt-1 text-sm font-medium tnum ${
                      quote.changePct >= 0 ? "text-up" : "text-down"
                    }`}
                  >
                    {signedPct(quote.changePct, 2)} on the session
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="mt-6">
            <SymbolSwitcher active={symbol} quotes={quotes} />
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-6xl space-y-5 px-5 pb-16 sm:px-8">
        {data.tableMissing && (
          <Notice
            title="Database migration pending"
            body={
              <>
                The <code className="text-ink">predictions</code> table does not exist yet.
                Apply <code className="text-ink">migrations/016_add_20d_horizon_and_predictions.sql</code>{" "}
                in the Supabase SQL editor, then run{" "}
                <code className="text-ink">python -m ml.src.predict.predict --backfill 2025-01-01</code>.
              </>
            }
          />
        )}

        {data.error && (
          <Notice title="Could not load predictions" body={<>{data.error}</>} />
        )}

        <section aria-label="Current outlook" className="grid gap-4 md:grid-cols-3">
          {HORIZONS.map((h) => (
            <HorizonCard key={h} horizon={h} prediction={data.latest[h]} accuracy={accuracyFor(h)} />
          ))}
        </section>

        <AccuracyPanel rows={data.accuracy} />

        <SignalChart bars={data.bars} predictions={data.history} />

        <HistoryTable rows={data.history} lastBarDate={data.lastBarDate} />

        <MethodNote />

        <footer className="space-y-3 pt-2 text-xs leading-relaxed text-ink-faint">
          <p className="max-w-3xl">
            Research project. Not investment advice, not a recommendation, and not a
            solicitation to trade.
          </p>
        </footer>
      </main>
    </div>
  );
}
