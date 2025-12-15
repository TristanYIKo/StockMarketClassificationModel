
import React from 'react';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface ProbabilityBarsProps {
    p_buy: number;
    p_hold: number;
    p_sell: number;
    className?: string;
}

export function ProbabilityBars({ p_buy, p_hold, p_sell, className }: ProbabilityBarsProps) {
    // Normalize checking (just in case)
    const total = p_buy + p_hold + p_sell || 1;
    const buyPct = (p_buy / total) * 100;
    const holdPct = (p_hold / total) * 100;
    const sellPct = (p_sell / total) * 100;

    return (
        <div className={cn("w-full space-y-2", className)}>
            <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-800">
                {/* BUY BAR */}
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div
                                className="h-full bg-emerald-500/80 hover:bg-emerald-400 transition-colors cursor-help"
                                style={{ width: `${buyPct}%` }}
                            />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Buy: {(p_buy * 100).toFixed(1)}%</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>

                {/* HOLD BAR */}
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div
                                className="h-full bg-slate-500/50 hover:bg-slate-400 transition-colors cursor-help border-l border-slate-900/20"
                                style={{ width: `${holdPct}%` }}
                            />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Hold: {(p_hold * 100).toFixed(1)}%</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>

                {/* SELL BAR */}
                <TooltipProvider>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div
                                className="h-full bg-rose-500/80 hover:bg-rose-400 transition-colors cursor-help border-l border-slate-900/20"
                                style={{ width: `${sellPct}%` }}
                            />
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Sell: {(p_sell * 100).toFixed(1)}%</p>
                        </TooltipContent>
                    </Tooltip>
                </TooltipProvider>
            </div>

            {/* Labels below for clarity */}
            <div className="flex justify-between text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                <span className="text-emerald-500">Buy {(p_buy * 100).toFixed(0)}%</span>
                <span className="text-slate-500">Hold {(p_hold * 100).toFixed(0)}%</span>
                <span className="text-rose-500">Sell {(p_sell * 100).toFixed(0)}%</span>
            </div>
        </div>
    );
}
