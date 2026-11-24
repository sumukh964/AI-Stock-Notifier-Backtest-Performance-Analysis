"""Backtest audit for AI Stock Notifier alerts.

Input: clean_alerts.csv (from clean_alerts.py).
Steps: load -> fetch prices -> returns from next open -> hit rate + significance test.

Run:
    pip install pandas yfinance scipy
    python backtest.py
"""
import argparse
import json
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf
from scipy.stats import binomtest

log = logging.getLogger("backtest")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--alerts", default="clean_alerts.csv")  # output of clean_alerts.py
    p.add_argument("--start", default="2026-05-13")
    p.add_argument("--end", default="2026-11-13")
    p.add_argument("--horizons", type=int, nargs="+", default=[1, 5, 20])
    p.add_argument("--benchmark", default="^NSEI")
    p.add_argument("--direction", choices=["alert", "headline"], default="alert",
                   help="alert = judge the alert as sent; headline = judge the headline direction")
    p.add_argument("--out", default="out")
    return p.parse_args()


def load_alerts(path, start, end, direction):
    df = pd.read_csv(path, parse_dates=["date"])
    df = df[df["date"].between(start, end)].copy()
    if direction == "headline":
        df = df[df["headline_direction"].isin(["rise", "fall"])]
        df["type"] = df["headline_direction"]
    df = df.rename(columns={"top_headline": "headline"})
    log.info("alerts used: %d", len(df))
    return df


def fetch_prices(symbols, start, end):
    prices = {}
    for sym in sorted(set(symbols)):
        px = yf.download(sym, start=start, end=end, auto_adjust=True, progress=False)
        if px.empty:
            log.warning("no price data: %s", sym)
            continue
        px.columns = px.columns.get_level_values(0)  # flatten yfinance columns
        prices[sym] = px[["Open", "Close"]].dropna()
    return prices


def window_return(px, entry_day, exit_day):
    return px.loc[exit_day, "Close"] / px.loc[entry_day, "Open"] - 1


def compute_returns(df, prices, benchmark, horizons):
    """Entry = open of the first trading day AFTER the alert date.
    Exit = close of the h-th trading day (entry day counts as day 1)."""
    bench = prices[benchmark]
    rows = []
    for r in df.itertuples():
        px = prices.get(r.ticker)
        if px is None:
            continue
        after = px.index[px.index > r.date]
        for h in horizons:
            if len(after) < h:
                continue  # not enough future data yet
            entry_day, exit_day = after[0], after[h - 1]
            if entry_day not in bench.index or exit_day not in bench.index:
                continue
            ret = window_return(px, entry_day, exit_day)
            bret = window_return(bench, entry_day, exit_day)
            rows.append({
                "date": r.date, "company": r.company, "ticker": r.ticker,
                "type": r.type, "confidence": r.confidence,
                "headline": r.headline, "horizon": h,
                "stock_ret": ret, "bench_ret": bret, "excess_ret": ret - bret,
            })
    return pd.DataFrame(rows)


def add_hits(res):
    """rise/buy is correct if excess > 0. fall is correct if excess < 0."""
    sign = res["type"].map(lambda t: -1 if t == "fall" else 1)
    res["hit"] = (res["excess_ret"] * sign) > 0
    res["signed_excess"] = res["excess_ret"] * sign
    return res


def summarize(res):
    def one(g):
        n, k = len(g), int(g["hit"].sum())
        return pd.Series({
            "n": n,
            "hit_rate": k / n,
            "avg_signed_excess_%": g["signed_excess"].mean() * 100,
            "p_value_vs_50%": binomtest(k, n, 0.5).pvalue,
        })
    by_type = res.groupby(["horizon", "type"]).apply(one)
    overall = res.groupby("horizon").apply(one)
    return overall, by_type


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)

    df = load_alerts(args.alerts, args.start, args.end, args.direction)
    fetch_end = pd.Timestamp.today() + pd.Timedelta(days=1)
    fetch_start = pd.Timestamp(args.start) - pd.Timedelta(days=5)
    prices = fetch_prices(list(df["ticker"]) + [args.benchmark], fetch_start, fetch_end)
    if args.benchmark not in prices:
        raise SystemExit("Benchmark prices missing. Check your internet connection.")

    res = add_hits(compute_returns(df, prices, args.benchmark, args.horizons))
    res.to_csv(out_dir / "results.csv", index=False)
    missing = sorted(set(df["ticker"]) - set(prices))
    if missing:
        log.warning("No price data for: %s (fix these tickers in tickers.csv)", missing)

    overall, by_type = summarize(res)
    overall.to_csv(out_dir / "summary_overall.csv")
    by_type.to_csv(out_dir / "summary_by_type.csv")
    print("\nOVERALL\n", overall.round(3))
    print("\nBY TYPE\n", by_type.round(3))


if __name__ == "__main__":
    main()
