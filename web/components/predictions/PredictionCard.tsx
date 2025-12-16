
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ProbabilityBars } from "./ProbabilityBars";
import { PredictionRow } from "./types";
import { Clock } from "lucide-react";

interface PredictionCardProps {
    title: string;
    prediction?: PredictionRow;
    isLoading?: boolean;
}

export function PredictionCard({ title, prediction, isLoading }: PredictionCardProps) {
    if (isLoading) {
        return (
            <Card className="bg-slate-900 border-slate-800 shadow-sm">
                <CardHeader className="pb-2">
                    <CardTitle className="text-slate-200 text-lg font-medium">{title}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Skeleton className="h-8 w-24 bg-slate-800 rounded-md" />
                    <Skeleton className="h-4 w-full bg-slate-800 rounded-md" />
                    <Skeleton className="h-3 w-3/4 bg-slate-800 rounded-md" />
                </CardContent>
            </Card>
        );
    }

    if (!prediction) {
        return (
            <Card className="bg-slate-900 border-slate-800 shadow-sm h-full flex flex-col justify-center items-center p-8 text-slate-500">
                <p>No data available</p>
            </Card>
        );
    }

    // Determine Badge Color
    const getBadgeColor = (dir: string) => {
        switch (dir) {
            case 'UP': return "bg-emerald-900/30 text-emerald-400 hover:bg-emerald-900/50 border-emerald-800/50";
            case 'DOWN': return "bg-rose-900/30 text-rose-400 hover:bg-rose-900/50 border-rose-800/50";
            default: return "bg-slate-800 text-slate-300 hover:bg-slate-700 border-slate-700";
        }
    };

    return (
        <Card className="bg-slate-900 border-slate-800 shadow-md overflow-hidden relative group">
            {/* Top accent line */}
            <div className={`absolute top-0 left-0 right-0 h-1 
        ${prediction.direction === 'UP' ? 'bg-emerald-500/50' : 'bg-rose-500/50'}`}
            />

            <CardHeader className="pb-2 pt-6">
                <div className="flex justify-between items-start">
                    <CardTitle className="text-slate-100 text-lg font-medium tracking-tight">
                        {title}
                    </CardTitle>
                    <Badge variant="outline" className={`text-sm px-3 py-1 font-semibold border ${getBadgeColor(prediction.direction)}`}>
                        {prediction.direction}
                    </Badge>
                </div>
            </CardHeader>

            <CardContent className="space-y-6">
                {/* Main Stats */}
                <div className="flex items-baseline space-x-2">
                    <span className="text-4xl font-bold text-slate-100">
                        {(prediction.confidence * 100).toFixed(0)}%
                    </span>
                    <span className="text-sm text-slate-500 font-medium uppercase tracking-wide">
                        Confidence
                    </span>
                </div>

                {/* Probability Visualization */}
                <div className="space-y-1">
                    <p className="text-xs text-slate-400 font-medium mb-2">Probability Distribution</p>
                    <ProbabilityBars
                        p_up={prediction.p_up}
                        p_down={prediction.p_down}
                    />
                </div>

                {/* Footer Meta */}
                <div className="pt-2 border-t border-slate-800/50 flex items-center text-xs text-slate-500">
                    <Clock className="w-3 h-3 mr-1.5" />
                    <span>
                        {prediction.date} • Model: XGBoost
                    </span>
                </div>
            </CardContent>
        </Card>
    );
}
