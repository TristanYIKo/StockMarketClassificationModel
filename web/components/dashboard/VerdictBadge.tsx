import { CircleCheck, CircleMinus, CircleAlert, Hourglass } from "lucide-react";
import { Verdict } from "@/lib/types";

/**
 * What the track record supports, in words and an icon -- never colour alone.
 * Only "beats chance" gets the positive tone: a horizon that merely sits near
 * 50% is reported neutrally, because that is what it is.
 */
export const VERDICT: Record<
  Verdict,
  { label: string; tone: string; dot: string; Icon: typeof CircleCheck; why: string }
> = {
  "beats-chance": {
    label: "Beats chance",
    tone: "border-up/40 bg-up-soft text-up",
    dot: "bg-up",
    Icon: CircleCheck,
    why: "The whole 95% range sits above 50%: these calls separate up from down.",
  },
  chance: {
    label: "No better than chance",
    tone: "border-line bg-surface text-ink-muted",
    dot: "bg-ink-muted",
    Icon: CircleMinus,
    why: "The 95% range includes 50%: a coin flip could have produced this record.",
  },
  worse: {
    label: "Worse than chance",
    tone: "border-down/40 bg-down-soft text-down",
    dot: "bg-down",
    Icon: CircleAlert,
    why: "The whole 95% range sits below 50%.",
  },
  "too-few": {
    label: "Too few events",
    tone: "border-line bg-surface text-ink-faint",
    dot: "bg-ink-faint",
    Icon: Hourglass,
    why: "Fewer than 30 independent outcomes: not enough evidence for a verdict.",
  },
};

export function VerdictBadge({ verdict, size = "sm" }: { verdict: Verdict; size?: "sm" | "xs" }) {
  const v = VERDICT[verdict];
  return (
    <span
      title={v.why}
      className={`inline-flex shrink-0 items-center gap-1 rounded-md border font-semibold ${v.tone} ${
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-1.5 py-px text-[10px]"
      }`}
    >
      <v.Icon aria-hidden className={size === "sm" ? "size-3.5" : "size-3"} strokeWidth={2.25} />
      {v.label}
    </span>
  );
}
