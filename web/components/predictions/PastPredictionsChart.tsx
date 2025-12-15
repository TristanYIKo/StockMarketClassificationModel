
"use client"

import React, { useState } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as RechartsTooltip,
    ResponsiveContainer,
    ReferenceDot
} from 'recharts';
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PredictionRow } from "./types";

interface PastPredictionsChartProps {
    data: PredictionRow[];
}

// Custom specialized tooltip
const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        const data = payload[0].payload;
        return (
            <div className="bg-slate-900 border border-slate-700 p-3 rounded-lg shadow-xl text-xs space-y-1 z-50">
                <p className="text-slate-200 font-semibold mb-1">{data.date}</p>
                <p className="text-slate-400">Close: <span className="text-slate-100">${data.close?.toFixed(2)}</span></p>
                <div className="my-1 border-t border-slate-800" />
                <p className={
                    data.direction === 'BUY' ? 'text-emerald-400' :
                        data.direction === 'SELL' ? 'text-rose-400' : 'text-slate-400'
                }>
                    Pred: {data.direction} ({(data.confidence * 100).toFixed(0)}%)
                </p>
                {data.actual_return !== undefined && (
                    <p className={data.actual_return > 0 ? 'text-emerald-500' : 'text-rose-500'}>
                        Return: {(data.actual_return * 100).toFixed(2)}%
                    </p>
                )}
            </div>
        );
    }
    return null;
};

// Custom dot structure
const CustomizedDot = (props: any) => {
    const { cx, cy, payload } = props;
    const dir = payload.direction;

    if (!dir) return null;

    if (dir === 'BUY') {
        return (
            <path
                d={`M${cx},${cy + 6} L${cx + 5},${cy - 4} L${cx - 5},${cy - 4} Z`}
                fill="#10b981"
                stroke="none"
            />
        ); // Up triangle
    }
    if (dir === 'SELL') {
        return (
            <path
                d={`M${cx},${cy - 4} L${cx + 5},${cy + 6} L${cx - 5},${cy + 6} Z`}
                fill="#f43f5e"
                stroke="none"
            />
        ); // Down triangle
    }
    return <circle cx={cx} cy={cy} r={3} fill="#94a3b8" stroke="none" />; // Hold dot
};

export function PastPredictionsChart({ data }: PastPredictionsChartProps) {
    const [horizon, setHorizon] = useState<'1d' | '5d'>('1d');

    // Filter data by selected horizon
    const filteredData = data.filter(d => d.horizon === horizon);

    return (
        <Card className="bg-slate-900 border-slate-800 shadow-md">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-6">
                <CardTitle className="text-slate-100 text-lg font-medium">
                    Past Predictions & Performance
                </CardTitle>
                <Tabs value={horizon} onValueChange={(v) => setHorizon(v as '1d' | '5d')} className="w-auto">
                    <TabsList className="bg-slate-950 border border-slate-800">
                        <TabsTrigger value="1d" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100">1-Day History</TabsTrigger>
                        <TabsTrigger value="5d" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100">5-Day History</TabsTrigger>
                    </TabsList>
                </Tabs>
            </CardHeader>
            <CardContent>
                <div className="h-[350px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={filteredData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                            <XAxis
                                dataKey="date"
                                tick={{ fill: '#64748b', fontSize: 11 }}
                                tickLine={false}
                                axisLine={false}
                                minTickGap={30}
                            />
                            <YAxis
                                domain={['auto', 'auto']}
                                tick={{ fill: '#64748b', fontSize: 11 }}
                                tickLine={false}
                                axisLine={false}
                                tickFormatter={(val) => `$${val}`}
                            />
                            <RechartsTooltip content={<CustomTooltip />} cursor={{ stroke: '#334155', strokeDasharray: '4 4' }} />

                            <Line
                                type="monotone"
                                dataKey="close"
                                stroke="#64748b"
                                strokeWidth={2}
                                dot={<CustomizedDot />}
                                activeDot={{ r: 6, fill: '#f8fafc' }}
                                animationDuration={1000}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Legend */}
                <div className="flex items-center justify-center space-x-6 mt-4 text-xs text-slate-400">
                    <div className="flex items-center">
                        <span className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-b-[8px] border-b-emerald-500 mr-2"></span>
                        Buy Signal
                    </div>
                    <div className="flex items-center">
                        <span className="w-2 h-2 rounded-full bg-slate-400 mr-2"></span>
                        Hold Signal
                    </div>
                    <div className="flex items-center">
                        <span className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[8px] border-t-rose-500 mr-2"></span>
                        Sell Signal
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
