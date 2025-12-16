
import React from 'react';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface ProbabilityBarsProps {
    p_up: number;
    p_down: number;
    className?: string;
}

export function ProbabilityBars({ p_up, p_down, className }: ProbabilityBarsProps) {
    // Normalize checking (just in case)
    const total = p_up + p_down || 1;
    const upPct = (p_up / total) * 100;
    const downPct = (p_down / total) * 100;

    return (
        <div className={cn("w-full space-y-2", className)}>
            <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-800">
                {/* UP BAR */}
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div
                                className="h-full bg-emerald-500/80 hover:bg-emerald-400 transition-colors cursor-help"
                                style={{ width: `${upPct}%` }}
                            />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Up: {(p_up * 100).toFixed(1)}%</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>

                {/* DOWN BAR */}
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div
                                className="h-full bg-rose-500/80 hover:bg-rose-400 transition-colors cursor-help border-l border-slate-900/20"
                                style={{ width: `${downPct}%` }}
                            />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Down: {(p_down * 100).toFixed(1)}%</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>

            {/* Labels below for clarity */}
            <div className="flex justify-between text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                <span className="text-emerald-500">Up {(p_up * 100).toFixed(0)}%</span>
                <span className="text-rose-500">Down {(p_down * 100).toFixed(0)}%</span>
            </div>
        </div>
    );
}
