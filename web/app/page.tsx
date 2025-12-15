
"use client"

import React, { useState, useEffect } from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PredictionCard } from "@/components/predictions/PredictionCard";
import { PastPredictionsTable } from "@/components/predictions/PastPredictionsTable";
import { PredictionRow } from "@/components/predictions/types";
import { Separator } from "@/components/ui/separator";
import { supabase } from "@/lib/supabase";

const SYMBOLS = ['SPY', 'QQQ', 'DIA', 'IWM'] as const;

export default function PredictionsPage() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('SPY');
  const [history, setHistory] = useState<PredictionRow[]>([]);
  const [currentPreds, setCurrentPreds] = useState<{ d1?: PredictionRow, d5?: PredictionRow }>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        // 1. Fetch Predictions
        const { data: preds, error: predError } = await supabase
          .from('model_predictions_classification')
          .select('*')
          .eq('symbol', selectedSymbol)
          .order('date', { ascending: false })
          .limit(100);

        if (predError) throw predError;

        // 2. Fetch Prices (OHLCV)
        const { data: assetData, error: assetError } = await supabase
          .from('assets')
          .select('id')
          .eq('symbol', selectedSymbol)
          .single();

        if (assetError || !assetData) throw new Error("Could not find asset ID.");

        const { data: prices, error: priceError } = await supabase
          .from('daily_bars')
          .select('date, open, high, low, close, volume')
          .eq('asset_id', assetData.id)
          .order('date', { ascending: false })
          .limit(120);

        if (priceError) throw priceError;

        // Create Price Map
        const priceMap = new Map<string, { o: number, h: number, l: number, c: number, v: number }>();
        prices?.forEach((p: any) => priceMap.set(p.date, { o: p.open, h: p.high, l: p.low, c: p.close, v: p.volume }));

        // Process Data
        const processed: PredictionRow[] = [];
        let latest1d: PredictionRow | undefined;
        let latest5d: PredictionRow | undefined;

        for (const p of preds || []) {
          const predDate = p.date;
          const bar = priceMap.get(predDate);

          // Validation Logic (Close-to-Close)
          const priceIndex = prices?.findIndex((x: any) => x.date === predDate);

          let outcomeClose: number | undefined;
          let actualRet: number | undefined;

          if (priceIndex !== undefined && priceIndex !== -1 && bar) {
            const jump = p.horizon === '1d' ? 1 : 5;
            const targetIndex = priceIndex - jump;

            if (targetIndex >= 0 && prices && prices[targetIndex]) {
              outcomeClose = prices[targetIndex].close;
              actualRet = Math.log(outcomeClose! / bar.c);
            }
          }

          const row: PredictionRow = {
            date: p.date,
            symbol: p.symbol,
            horizon: p.horizon,
            direction: getDirection(p.pred_class_final),
            p_buy: p.p_buy,
            p_hold: p.p_hold,
            p_sell: p.p_sell,
            confidence: p.confidence,
            close: bar?.c, // Close price
            actual_return: actualRet,
          };

          processed.push(row);

          if (p.horizon === '1d' && !latest1d) latest1d = row;
          if (p.horizon === '5d' && !latest5d) latest5d = row;
        }

        setHistory(processed);
        setCurrentPreds({ d1: latest1d, d5: latest5d });

      } catch (err: any) {
        console.error("Fetch error:", err);
        setError(err.message || "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [selectedSymbol]);

  function getDirection(val: number): 'BUY' | 'HOLD' | 'SELL' {
    if (val === 1) return 'BUY';
    if (val === -1) return 'SELL';
    return 'HOLD';
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-emerald-500/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">

        {/* Error Banner */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-200 px-4 py-3 rounded-md text-sm">
            <p className="font-semibold">Connection Error</p>
            <p>{error}. Please check your internet connection or VPN.</p>
          </div>
        )}

        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-white mb-1">Market Intelligence</h1>
            <p className="text-slate-400 text-sm">AI-driven classification models.</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-[140px]">
              <Select value={selectedSymbol} onValueChange={setSelectedSymbol}>
                <SelectTrigger className="bg-slate-900 border-slate-700 text-slate-200 h-9">
                  <SelectValue placeholder="Symbol" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-800 text-slate-200">
                  {SYMBOLS.map(sym => <SelectItem key={sym} value={sym}>{sym}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Tabs defaultValue="30d" className="hidden sm:block">
              <TabsList className="bg-slate-900 border border-slate-800 h-9">
                <TabsTrigger value="30d" className="text-xs">30 Days</TabsTrigger>
                <TabsTrigger value="90d" className="text-xs">90 Days</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </header>
        <Separator className="bg-slate-800/50" />

        <section className="grid md:grid-cols-2 gap-6">
          <PredictionCard title="1-Day Outlook" prediction={currentPreds.d1} isLoading={loading} />
          <PredictionCard title="5-Day Outlook" prediction={currentPreds.d5} isLoading={loading} />
        </section>

        <section>
          <PastPredictionsTable data={history} />
        </section>
        <footer className="text-center text-slate-600 text-xs py-8">
          <p>Generated by Antigravity AI • Not financial advice.</p>
        </footer>
      </div>
    </div>
  );
}
