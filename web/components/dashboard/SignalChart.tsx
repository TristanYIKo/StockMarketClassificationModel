"use client";

import { useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Bar, HORIZONS, HORIZON_LABEL, Horizon, Prediction } from "@/lib/types";
import { shortDate, usd, pct } from "@/lib/format";
import { Segmented } from "@/components/ui/segmented";

type Point = Bar & {
  call?: 1 | -1;
  confidence?: number;
  correct?: boolean | null;
};

/**
 * Markers are drawn on the as_of_date -- the session the call was made from --
 * not the target date, so a marker sits at the price the model actually saw.
 */
function SignalDot(props: {
  cx?: number;
  cy?: number;
  payload?: Point;
}) {
  const { cx, cy, payload } = props;
  if (!payload?.call || cx === undefined || cy === undefined) return null;

  const up = payload.call === 1;
  const fill = up ? "var(--color-up)" : "var(--color-down)";
  const y = up ? cy - 7 : cy + 7;
  const r = 3.4;
  const d = up
    ? `M${cx},${y - r} L${cx + r},${y + r * 0.75} L${cx - r},${y + r * 0.75} Z`
    : `M${cx},${y + r} L${cx + r},${y - r * 0.75} L${cx - r},${y - r * 0.75} Z`;

  // One marker per session is a lot of ink over 180 days. Confidence drives
  // opacity so the strong calls read first and the line stays legible beneath,
  // and wrong calls are dimmed further.
  // Confidence on this task clusters near 0.5-0.7, so the ramp starts from a
  // visible floor rather than scaling from zero -- otherwise almost every
  // marker bottoms out and the signal layer disappears entirely.
  const conf = payload.confidence ?? 0.5;
  const strength = Math.min(1, 0.5 + (conf - 0.5) * 2.5);
  const opacity = payload.correct === false ? strength * 0.5 : strength;

  return <path d={d} fill={fill} opacity={opacity} />;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: Point }>;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;

  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-xl">
      <p className="font-medium text-ink">{shortDate(p.date)}</p>
      <p className="mt-1 tnum text-ink-muted">Close {usd(p.close)}</p>
      {p.call && (
        <p className={`mt-1 font-medium ${p.call === 1 ? "text-up" : "text-down"}`}>
          Called {p.call === 1 ? "UP" : "DOWN"} · {pct(p.confidence, 0)}
          {p.correct === null || p.correct === undefined
            ? " · pending"
            : p.correct
              ? " · hit"
              : " · miss"}
        </p>
      )}
    </div>
  );
}

export function SignalChart({
  bars,
  predictions,
}: {
  bars: Bar[];
  predictions: Prediction[];
}) {
  const [horizon, setHorizon] = useState<Horizon>("1d");

  const data: Point[] = useMemo(() => {
    const byDate = new Map<string, Prediction>();
    for (const p of predictions) {
      if (p.horizon === horizon) byDate.set(p.as_of_date, p);
    }
    return bars.map((b) => {
      const p = byDate.get(b.date);
      return p
        ? { ...b, call: p.pred_class, confidence: p.confidence, correct: p.is_correct }
        : { ...b };
    });
  }, [bars, predictions, horizon]);

  const marked = data.filter((d) => d.call).length;

  return (
    <section className="card p-5" aria-labelledby="chart-heading">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="chart-heading" className="text-sm font-semibold text-ink">
            Price and signals
          </h2>
          <p className="mt-0.5 text-[11px] text-ink-faint">
            {bars.length} sessions · {marked} marked calls
          </p>
        </div>

        <Segmented
          label="Chart horizon"
          value={horizon}
          onChange={setHorizon}
          options={HORIZONS.map((h) => ({ value: h, label: HORIZON_LABEL[h] }))}
        />
      </header>

      <div className="h-[320px] w-full">
        {bars.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-ink-faint">
            No price history available.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-accent)" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="var(--color-accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--color-line-soft)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "var(--color-ink-faint)", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={44}
                tickFormatter={(v: string) => v.slice(5)}
              />
              <YAxis
                domain={["dataMin - 12", "dataMax + 12"]}
                tick={{ fill: "var(--color-ink-faint)", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(v: number) => `$${Math.round(v)}`}
              />
              <Tooltip
                content={<ChartTooltip />}
                cursor={{ stroke: "var(--color-line)", strokeDasharray: "4 4" }}
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke="none"
                fill="url(#priceFill)"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="close"
                stroke="var(--color-accent)"
                strokeWidth={1.75}
                dot={<SignalDot />}
                activeDot={{ r: 4, fill: "var(--color-ink)", stroke: "var(--color-base)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-line pt-3 text-[11px] text-ink-faint">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0 w-0 border-x-4 border-b-[7px] border-x-transparent border-b-up" />
          Called up
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0 w-0 border-x-4 border-t-[7px] border-x-transparent border-t-down" />
          Called down
        </span>
        <span>Brighter = higher confidence · faded = wrong call</span>
      </div>
    </section>
  );
}
