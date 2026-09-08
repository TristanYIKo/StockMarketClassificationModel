import { supabase } from "@/lib/supabase";
import {
  Accuracy,
  Bar,
  Dashboard,
  HORIZONS,
  Horizon,
  Prediction,
  Quote,
  SYMBOLS,
  Symbol,
} from "@/lib/types";

/** How many predictions per horizon back the table, chart markers and hit rate. */
const HISTORY_PER_HORIZON = 200;
const BAR_WINDOW = 180;

/**
 * Postgres error raised when a relation does not exist. The `predictions` table
 * arrives with migration 016, so until that is applied the dashboard should say
 * so plainly rather than render an error page.
 */
const UNDEFINED_TABLE = new Set(["42P01", "PGRST205"]);

const HORIZON_DAYS: Record<Horizon, number> = { "1d": 1, "5d": 5, "20d": 20 };

function summarise(rows: Prediction[], horizon: Horizon): Accuracy {
  const forHorizon = rows.filter((r) => r.horizon === horizon);
  const resolved = forHorizon.filter((r) => r.y_true !== null);
  const hits = resolved.filter((r) => r.is_correct === true).length;

  // The bar to clear: how often the market actually closed up over these same
  // windows. Quoting accuracy without it would flatter the model, since index
  // direction is up far more often than not.
  const ups = resolved.filter((r) => r.y_true === 1).length;

  const conf = forHorizon.length
    ? forHorizon.reduce((a, r) => a + r.confidence, 0) / forHorizon.length
    : null;

  // Balanced accuracy: recall on up-days and down-days, averaged. Computed here
  // rather than read from a view so it always matches the rows on screen.
  const pos = resolved.filter((r) => r.y_true === 1);
  const neg = resolved.filter((r) => r.y_true === -1);
  const balanced =
    pos.length && neg.length
      ? (pos.filter((r) => r.pred_class === 1).length / pos.length +
          neg.filter((r) => r.pred_class === -1).length / neg.length) /
        2
      : null;

  return {
    horizon,
    resolved: resolved.length,
    hits,
    accuracy: resolved.length ? hits / resolved.length : null,
    baseline: resolved.length ? ups / resolved.length : null,
    balancedAccuracy: balanced,
    upRate: forHorizon.length
      ? forHorizon.filter((r) => r.pred_class === 1).length / forHorizon.length
      : null,
    // Distinct as-of dates divided by the horizon: overlapping windows and four
    // correlated ETFs mean the row count badly overstates the sample.
    effectiveEvents: resolved.length
      ? Math.max(
          1,
          Math.floor(new Set(resolved.map((r) => r.as_of_date)).size / HORIZON_DAYS[horizon]),
        )
      : null,
    avgConfidence: conf,
  };
}

async function getBars(symbol: Symbol): Promise<{ bars: Bar[]; lastBarDate: string | null }> {
  const asset = await supabase.from("assets").select("id").eq("symbol", symbol).single();
  if (!asset.data?.id) return { bars: [], lastBarDate: null };

  const rows = await supabase
    .from("daily_bars")
    .select("date, close")
    .eq("asset_id", asset.data.id)
    .order("date", { ascending: false })
    .limit(BAR_WINDOW);

  const bars = ((rows.data ?? []) as Bar[])
    .filter((b) => b.close !== null)
    .map((b) => ({ date: b.date, close: Number(b.close) }))
    .reverse();

  return { bars, lastBarDate: bars.at(-1)?.date ?? null };
}

export async function getDashboard(symbol: Symbol): Promise<Dashboard> {
  const empty: Dashboard = {
    symbol,
    latest: {},
    history: [],
    bars: [],
    accuracy: [],
    lastBarDate: null,
    tableMissing: false,
    error: null,
  };

  // Prices first, and independently: they come from daily_bars, which exists
  // regardless of whether the predictions migration has been applied. Fetching
  // them before the bail-out below means the chart still renders in that state.
  const { bars, lastBarDate } = await getBars(symbol);

  // Predictions, newest first, capped per horizon so one horizon cannot crowd
  // the others out of the window.
  const perHorizon = await Promise.all(
    HORIZONS.map((h) =>
      supabase
        .from("predictions")
        .select(
          "symbol, horizon, as_of_date, target_date, model_name, pred_class, p_up, p_down, confidence, margin, as_of_close, outcome_close, actual_return, y_true, is_correct",
        )
        .eq("symbol", symbol)
        .eq("horizon", h)
        .eq("split", "production")
        .order("as_of_date", { ascending: false })
        .limit(HISTORY_PER_HORIZON),
    ),
  );

  const failure = perHorizon.find((r) => r.error);
  if (failure?.error) {
    if (UNDEFINED_TABLE.has(failure.error.code ?? "")) {
      return { ...empty, bars, lastBarDate, tableMissing: true };
    }
    return { ...empty, bars, lastBarDate, error: failure.error.message };
  }

  const history = perHorizon.flatMap((r) => (r.data ?? []) as Prediction[]);

  const latest: Partial<Record<Horizon, Prediction>> = {};
  for (const h of HORIZONS) {
    latest[h] = history
      .filter((r) => r.horizon === h)
      .sort((a, b) => b.as_of_date.localeCompare(a.as_of_date))[0];
  }

  return {
    ...empty,
    latest,
    history,
    bars,
    accuracy: HORIZONS.map((h) => summarise(history, h)),
    lastBarDate,
  };
}


/**
 * Last close and one-session change for every instrument.
 *
 * Powers the header strip, so the symbol selector carries real information
 * rather than being four inert labels. Cheap: two rows per symbol.
 */
export async function getQuotes(): Promise<Quote[]> {
  const assets = await supabase.from("assets").select("id, symbol").in("symbol", [...SYMBOLS]);
  const idBySymbol = new Map<string, string>(
    (assets.data ?? []).map((a: { id: string; symbol: string }) => [a.symbol, a.id]),
  );

  return Promise.all(
    SYMBOLS.map(async (symbol): Promise<Quote> => {
      const id = idBySymbol.get(symbol);
      if (!id) return { symbol, close: null, changePct: null };

      const rows = await supabase
        .from("daily_bars")
        .select("date, close")
        .eq("asset_id", id)
        .order("date", { ascending: false })
        .limit(2);

      const bars = (rows.data ?? []) as Bar[];
      const latest = bars[0]?.close != null ? Number(bars[0].close) : null;
      const prior = bars[1]?.close != null ? Number(bars[1].close) : null;

      return {
        symbol,
        close: latest,
        changePct: latest !== null && prior ? latest / prior - 1 : null,
      };
    }),
  );
}
