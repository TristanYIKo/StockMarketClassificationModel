import Link from "next/link";
import { Quote, SYMBOLS, SYMBOL_NAME, Symbol } from "@/lib/types";
import { signedPct, usd } from "@/lib/format";

/**
 * Instrument selector.
 *
 * Selection is a link, not client state: the page is server-rendered per symbol,
 * so the URL stays shareable and the back button behaves.
 *
 * The active tile is distinguished on four channels at once -- background,
 * border, a filled accent rail, and text weight -- because the previous version
 * relied on a single 10%-opacity tint that was invisible against the dark
 * surface. Each tile also carries its own quote, so the strip is a market
 * overview rather than four inert labels.
 */
export function SymbolSwitcher({
  active,
  quotes = [],
}: {
  active: Symbol;
  // Defaulted: the strip must still render its tiles if the quote query fails,
  // since it is the page's only navigation.
  quotes?: Quote[];
}) {
  const bySymbol = new Map(quotes.map((q) => [q.symbol, q]));

  return (
    <nav aria-label="Select instrument">
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {SYMBOLS.map((sym) => {
          const isActive = sym === active;
          const quote = bySymbol.get(sym);
          const up = (quote?.changePct ?? 0) >= 0;

          return (
            <li key={sym}>
              <Link
                href={`/?symbol=${sym}`}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "group relative block overflow-hidden rounded-xl border px-4 py-3",
                  "transition-all duration-200 ease-out",
                  "hover:-translate-y-0.5 focus-visible:-translate-y-0.5",
                  isActive
                    ? "border-accent/60 bg-surface-2 shadow-[0_0_0_1px_rgba(76,141,255,0.25),0_8px_24px_-12px_rgba(76,141,255,0.55)]"
                    : "border-line bg-surface hover:border-ink-faint/50 hover:bg-surface-2",
                ].join(" ")}
              >
                {/* Filled rail: the strongest single cue for the active tile. */}
                <span
                  aria-hidden
                  className={[
                    "absolute inset-y-0 left-0 w-[3px] transition-colors duration-200",
                    isActive ? "bg-accent" : "bg-transparent group-hover:bg-line",
                  ].join(" ")}
                />

                <div className="flex items-baseline justify-between gap-2">
                  <span
                    className={[
                      "text-[15px] font-bold tracking-tight transition-colors",
                      isActive ? "text-ink" : "text-ink-muted group-hover:text-ink",
                    ].join(" ")}
                  >
                    {sym}
                  </span>
                  {quote?.changePct !== null && quote?.changePct !== undefined && (
                    <span
                      className={`text-[11px] font-semibold tnum ${up ? "text-up" : "text-down"}`}
                    >
                      {signedPct(quote.changePct, 2)}
                    </span>
                  )}
                </div>

                <div className="mt-0.5 flex items-baseline justify-between gap-2">
                  <span className="truncate text-[11px] text-ink-faint">
                    {SYMBOL_NAME[sym]}
                  </span>
                  <span
                    className={[
                      "text-[11px] tnum transition-colors",
                      isActive ? "text-ink-muted" : "text-ink-faint",
                    ].join(" ")}
                  >
                    {quote?.close != null ? usd(quote.close) : "—"}
                  </span>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
