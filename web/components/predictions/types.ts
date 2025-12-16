
export type PredictionRow = {
    date: string;              // 'YYYY-MM-DD'
    symbol: 'SPY' | 'QQQ' | 'DIA' | 'IWM';
    horizon: '1d' | '5d';
    direction: 'UP' | 'DOWN';
    p_up: number;              // 0..1
    p_down: number;            // 0..1
    confidence: number;        // max prob
    close?: number;            // for chart
    actual_return?: number;    // optional for past days
    correct?: boolean;         // optional for past days
    created_at?: string;       // optional
};
