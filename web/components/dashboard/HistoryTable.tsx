"use client";

import { useMemo, useState } from "react";
import { HORIZONS, HORIZON_LABEL, Horizon, Prediction } from "@/lib/types";
import { shortDate, signedPct, usd, pct } from "@/lib/format";
import { Segmented } from "@/components/ui/segmented";

export function HistoryTable({ rows }: { rows: Prediction[] }) {
  const [horizon, setHorizon] = useState<Horizon>("1d");

  const filtered = useMemo(
    () =>
      rows
        .filter((r) => r.horizon === horizon)
        .sort((a, b) => b.as_of_date.localeCompare(a.as_of_date))
        .slice(0, 60),
    [rows, horizon],
  );

  return (
    <section className="card overflow-hidden" aria-labelledby="history-heading">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
        <div>
          <h2 id="history-heading" className="text-sm font-semibold text-ink">
            Prediction history
          </h2>
          <p className="mt-0.5 text-[11px] text-ink-faint">
            Each row is one call and the outcome it was scored against
          </p>
        </div>

        <Segmented
          label="Horizon"
          value={horizon}
          onChange={setHorizon}
          options={HORIZONS.map((h) => ({ value: h, label: HORIZON_LABEL[h] }))}
        />
      </header>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[46rem] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-ink-faint">
              <th scope="col" className="px-5 py-2.5 font-medium">Predicted on</th>
              <th scope="col" className="px-5 py-2.5 font-medium">Resolves</th>
              <th scope="col" className="px-5 py-2.5 font-medium">Call</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Conf.</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Entry</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Outcome</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Return</th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">Result</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-5 py-14 text-center text-ink-faint">
                  No {HORIZON_LABEL[horizon].toLowerCase()} predictions stored yet.
                </td>
              </tr>
            ) : (
              filtered.map((r) => {
                const isUp = r.pred_class === 1;
                const pending = r.y_true === null;

                return (
                  <tr
                    key={`${r.as_of_date}-${r.horizon}`}
                    className="border-b border-line-soft last:border-0 hover:bg-surface-2/60"
                  >
                    <td className="px-5 py-2.5 tnum text-ink-muted">
                      {shortDate(r.as_of_date)}
                    </td>
                    <td className="px-5 py-2.5 tnum text-ink-faint">
                      {shortDate(r.target_date)}
                    </td>
                    <td className="px-5 py-2.5">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[11px] font-bold ${
                          isUp ? "bg-up-soft text-up" : "bg-down-soft text-down"
                        }`}
                      >
                        {isUp ? "UP" : "DOWN"}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-right tnum text-ink-muted">
                      {pct(r.confidence, 0)}
                    </td>
                    <td className="px-5 py-2.5 text-right tnum text-ink-muted">
                      {usd(r.as_of_close)}
                    </td>
                    <td className="px-5 py-2.5 text-right tnum text-ink-muted">
                      {pending ? "—" : usd(r.outcome_close)}
                    </td>
                    <td
                      className={`px-5 py-2.5 text-right tnum ${
                        r.actual_return === null
                          ? "text-ink-faint"
                          : r.actual_return > 0
                            ? "text-up"
                            : "text-down"
                      }`}
                    >
                      {signedPct(r.actual_return)}
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      {pending ? (
                        <span className="text-[11px] text-pending">Pending</span>
                      ) : r.is_correct ? (
                        <span className="text-[11px] font-medium text-up">Hit</span>
                      ) : (
                        <span className="text-[11px] font-medium text-down">Miss</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
