export const SYMBOLS = ["SPY", "QQQ", "DIA", "IWM"] as const;
export type Symbol = (typeof SYMBOLS)[number];

export const HORIZONS = ["1d", "5d", "20d"] as const;
export type Horizon = (typeof HORIZONS)[number];

export const HORIZON_LABEL: Record<Horizon, string> = {
  "1d": "1 Day",
  "5d": "5 Days",
  "20d": "20 Days",
};

export const SYMBOL_NAME: Record<Symbol, string> = {
  SPY: "S&P 500",
  QQQ: "Nasdaq 100",
  DIA: "Dow 30",
  IWM: "Russell 2000",
};

/** One row of public.predictions. */
export type Prediction = {
  symbol: Symbol;
  horizon: Horizon;
  /** Session whose close the features describe. The call is made after this close. */
  as_of_date: string;
  /** Session being predicted: as_of_date advanced by `horizon` trading days. */
  target_date: string;
  model_name: string;
  pred_class: 1 | -1;
  p_up: number;
  p_down: number;
  confidence: number;
  margin: number;
  as_of_close: number | null;
  outcome_close: number | null;
  actual_return: number | null;
  y_true: 1 | -1 | null;
  is_correct: boolean | null;
};

export type Bar = {
  date: string;
  close: number;
};

/** Realised performance for one symbol/horizon. */
export type Accuracy = {
  horizon: Horizon;
  resolved: number;
  hits: number;
  /** Plain hit rate. Dominated by the base rate, so never shown on its own. */
  accuracy: number | null;
  /** Share of resolved windows that actually closed up: the always-UP baseline. */
  baseline: number | null;
  /**
   * Mean of per-class recall. The headline number, because it is the one the
   * base rate cannot inflate: a model that always says UP scores 0.50 here no
   * matter how good its plain accuracy looks. Above 0.50 means the model is
   * genuinely separating up-days from down-days.
   */
  balancedAccuracy: number | null;
  /** Share of predictions that were UP. Near 0 or 1 means a collapsed model. */
  upRate: number | null;
  /**
   * Independent events behind `resolved`. Consecutive h-day windows overlap in
   * h-1 of their days, so 180 resolved 20-day calls describe only ~9 distinct
   * outcomes. Quoting the raw count would imply precision that is not there.
   */
  effectiveEvents: number | null;
  avgConfidence: number | null;
};

export type Dashboard = {
  symbol: Symbol;
  latest: Partial<Record<Horizon, Prediction>>;
  history: Prediction[];
  bars: Bar[];
  accuracy: Accuracy[];
  lastBarDate: string | null;
  tableMissing: boolean;
  error: string | null;
};

/** Latest quote for one instrument, used by the header strip. */
export type Quote = {
  symbol: Symbol;
  close: number | null;
  /** Simple return versus the previous session's close. */
  changePct: number | null;
};
