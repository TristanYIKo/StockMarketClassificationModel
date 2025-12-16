
"use client"

import React, { useState } from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PredictionRow } from "./types";
import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";

interface PastPredictionsTableProps {
    data: PredictionRow[];
}

export function PastPredictionsTable({ data }: PastPredictionsTableProps) {
    const [horizon, setHorizon] = useState<'1d' | '5d'>('1d');

    // Filter data by selected horizon & sort by date descending
    const filteredData = data
        .filter(d => d.horizon === horizon)
        .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    const getBadgeColor = (dir: string) => {
        switch (dir) {
            case 'UP': return "bg-emerald-900/30 text-emerald-400 border-emerald-800/50";
            case 'DOWN': return "bg-rose-900/30 text-rose-400 border-rose-800/50";
            default: return "bg-slate-800 text-slate-300 border-slate-700";
        }
    };

    return (
        <Card className="bg-slate-900 border-slate-800 shadow-md">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-6">
                <CardTitle className="text-slate-100 text-lg font-medium">
                    Past Predictions & Results
                </CardTitle>
                <Tabs value={horizon} onValueChange={(v) => setHorizon(v as '1d' | '5d')} className="w-auto">
                    <TabsList className="bg-slate-950 border border-slate-800">
                        <TabsTrigger value="1d" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100">1-Day History</TabsTrigger>
                        <TabsTrigger value="5d" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100">5-Day History</TabsTrigger>
                    </TabsList>
                </Tabs>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border border-slate-800">
                    <Table>
                        <TableHeader className="bg-slate-950">
                            <TableRow className="border-slate-800 hover:bg-slate-900/50">
                                <TableHead className="text-slate-400 w-[120px]">Date</TableHead>
                                <TableHead className="text-slate-400">Close Price</TableHead>
                                <TableHead className="text-slate-400">Prediction</TableHead>
                                <TableHead className="text-slate-400">Confidence</TableHead>
                                <TableHead className="text-slate-400 text-right">Outcome</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredData.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={5} className="h-24 text-center text-slate-500">
                                        No history available.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filteredData.map((row, idx) => (
                                    <TableRow key={idx} className="border-slate-800 hover:bg-slate-800/30">
                                        <TableCell className="font-medium text-slate-300">{row.date}</TableCell>
                                        <TableCell className="text-slate-400 font-mono">
                                            ${row.close?.toFixed(2) ?? '---'}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline" className={`border ${getBadgeColor(row.direction)}`}>
                                                {row.direction}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-slate-400">
                                            {(row.confidence * 100).toFixed(1)}% <span className="text-slate-600 text-xs ml-1">(Prob)</span>
                                        </TableCell>
                                        <TableCell className="text-right flex justify-end items-center gap-2">
                                            {/* Logic for outcome checking would go here. For now simpler display */}
                                            {row.actual_return !== undefined ? (
                                                <div className={`flex items-center gap-1.5 ${row.actual_return > 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                                                    <span className="font-mono">{(row.actual_return * 100).toFixed(2)}%</span>
                                                    {row.direction === 'UP' && row.actual_return > 0 ? <CheckCircle2 className="w-4 h-4" /> :
                                                        row.direction === 'DOWN' && row.actual_return < 0 ? <CheckCircle2 className="w-4 h-4" /> :
                                                            <XCircle className="w-4 h-4 text-slate-500" />}
                                                </div>
                                            ) : (
                                                <span className="text-slate-600 flex items-center gap-1 justify-end">
                                                    Pending <MinusCircle className="w-4 h-4" />
                                                </span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
}
