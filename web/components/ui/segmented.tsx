"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Segmented control with a sliding indicator.
 *
 * The indicator's position and width are MEASURED from the active button rather
 * than assumed to be an equal 1/n slot. Labels here differ in width ("1 Day" vs
 * "20 Days"), and `flex-1` only equalises the free space, not the total width,
 * so an equal-slot indicator drifted several pixels off its button. Measuring
 * makes it exact for any set of labels.
 *
 * The measurement re-runs on resize and on font load, since both change button
 * widths after first paint.
 */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef(new Map<T, HTMLButtonElement>());
  const [box, setBox] = useState<{ left: number; width: number } | null>(null);

  const measure = useCallback(() => {
    const track = trackRef.current;
    const active = buttonRefs.current.get(value);
    if (!track || !active) return;
    setBox({ left: active.offsetLeft, width: active.offsetWidth });
  }, [value]);

  useLayoutEffect(measure, [measure]);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(track);
    document.fonts?.ready.then(measure).catch(() => {});
    return () => ro.disconnect();
  }, [measure]);

  return (
    <div className="inline-block rounded-lg border border-line bg-base p-1">
      <div ref={trackRef} role="tablist" aria-label={label} className="relative flex">
        {box && (
          <span
            aria-hidden
            className="absolute inset-y-0 rounded-md bg-surface-2 ring-1 ring-line transition-[left,width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
            style={{ left: box.left, width: box.width }}
          />
        )}
        {options.map((opt) => {
          const active = opt.value === value;
          return (
            <button
              key={opt.value}
              ref={(el) => {
                if (el) buttonRefs.current.set(opt.value, el);
                else buttonRefs.current.delete(opt.value);
              }}
              role="tab"
              type="button"
              aria-selected={active}
              onClick={() => onChange(opt.value)}
              className={[
                "relative z-10 whitespace-nowrap rounded-md px-3 py-1.5",
                "text-xs font-medium transition-colors duration-200",
                active ? "text-ink" : "text-ink-faint hover:text-ink-muted",
              ].join(" ")}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
