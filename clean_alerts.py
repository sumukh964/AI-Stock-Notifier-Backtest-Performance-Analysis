"""Clean the AI Stock Notifier alert log.

Input : alerts.json, tickers.csv (alias map), rules.json (config)
Output: clean_alerts.csv, rejected_alerts.csv, cleaning_report.md

Steps
 1. Load, parse dates, keep date range + signal types.
 2. Normalise the company text.
 3. Map to an NSE ticker: company field first, then the headline.
 4. Reject non-stocks (index, broker, foreign, amount, unknown).
 5. Remove repeated alerts (same ticker + same headline).
 6. Check the alert label against the headline.
"""
import argparse
import json
import re
from pathlib import Path

import pandas as pd


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--alerts", default="alerts.json")
    p.add_argument("--tickers", default="tickers.csv")
    p.add_argument("--rules", default="rules.json")
    p.add_argument("--out", default=".")
    return p.parse_args()


# ---------- text helpers ----------
def norm(s):
    s = str(s).lower().replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"\s+", " ", s).strip()
    for _ in range(3):
        s = re.sub(r"\s+q[1-4](\s+fy\d+)?$", "", s)
        s = re.sub(r"\s+fy\d+$", "", s)
        s = s.rstrip(":,.;'").strip()
    return s


def word_search(alias, text):
    m = re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text)
    return m.start() if m else -1


# ---------- steps ----------
def load(path, rules):
    df = pd.DataFrame(json.loads(Path(path).read_text(encoding="utf-8")))
    df["alert_id"] = df.index
    df["date"] = pd.to_datetime(df["date"])
    n_all = len(df)
    df = df[df["type"].isin(rules["signal_types"])]
    n_sig = len(df)
    df = df[df["date"].between(rules["date_start"], rules["date_end"])].copy()
    return df, n_all, n_sig


def build_alias(tickers_path):
    t = pd.read_csv(tickers_path)
    t["key"] = t["company"].map(norm)
    t = t.drop_duplicates("key")
    exact = dict(zip(t["key"], t["ticker"]))
    hl = t[t["headline_match"] == "yes"]
    hl_list = sorted(zip(hl["key"], hl["ticker"]), key=lambda x: -len(x[0]))
    return exact, hl_list


def classify_non_stock(key, rules):
    ns = rules["non_stock"]
    if re.match(ns["amount_regex"], key):
        return "amount_not_company"
    for reason, names in ns.items():
        if reason != "amount_regex" and key in names:
            return reason
    return "unknown_or_unlisted"


def map_ticker(row, exact, hl_list, rules):
    """Return (ticker, source, reject_reason).
    Headline lookup is used ONLY when the company field is not a stock
    (broker, amount, index word...) AND the headline names exactly one known stock.
    A real but unmapped company is rejected."""
    key = row["company_norm"]
    if key in exact:
        return exact[key], "company_field", None
    if not key:
        return None, None, "no_company"
    text0 = norm(row["top_headline"]) if isinstance(row["top_headline"], str) else ""
    if any(x in text0 for x in rules.get("manual_exclude_headlines", [])):
        return None, None, "manual_exclude_wrong_subject"
    reason = classify_non_stock(key, rules)
    if reason == "unknown_or_unlisted":
        return None, None, reason
    text = norm(row["top_headline"]) if isinstance(row["top_headline"], str) else ""
    found = {tk for alias, tk in hl_list if word_search(alias, text) >= 0}
    if len(found) == 1:
        return found.pop(), "headline", None
    return None, None, ("ambiguous_headline_several_stocks" if found else reason)


def split_multi(df, exact):
    """'Mphasis, Coforge' -> two rows, if every part is a known stock."""
    rows = []
    for r in df.to_dict("records"):
        key = r["company_norm"]
        parts = [p.strip() for p in key.split(",")] if "," in key else []
        if key not in exact and len(parts) > 1 and all(p in exact for p in parts):
            for p in parts:
                rows.append({**r, "company_norm": p})
        else:
            rows.append(r)
    return pd.DataFrame(rows)


def headline_direction(row, ticker_alias, rules):
    """Direction of the clause in the headline that talks about this stock."""
    h = row["top_headline"]
    if not isinstance(h, str):
        return "n/a"
    text = norm(h)
    clauses = [c for c in re.split(r"[;|]", text) if c.strip()]
    clause = next((c for c in clauses if any(word_search(a, c) >= 0 for a in ticker_alias)), text)
    clause = clause.split(":", 1)[-1]
    up = sum(word_search(w, clause) >= 0 for w in rules["up_words"])
    down = sum(word_search(w, clause) >= 0 for w in rules["down_words"])
    down += sum(bool(re.search(r, clause)) for r in rules["down_regex"])
    if up and not down:
        return "rise"
    if down and not up:
        return "fall"
    return "unclear"


def parse_score(s):
    m = re.search(r"avg score ([+-]?\d+\.\d+)", str(s))
    return float(m.group(1)) if m else None


def main():
    a = args()
    rules = json.loads(Path(a.rules).read_text())
    out = Path(a.out)
    df, n_all, n_sig = load(a.alerts, rules)
    n_range = len(df)

    df["company_norm"] = df["company"].map(lambda x: norm(x) if isinstance(x, str) else "")
    exact, hl_list = build_alias(a.tickers)
    ticker_to_alias = {}
    for k, t in list(exact.items()) + hl_list:
        ticker_to_alias.setdefault(t, []).append(k)

    df = split_multi(df, exact)
    res = df.apply(lambda r: map_ticker(r, exact, hl_list, rules), axis=1, result_type="expand")
    df["ticker"], df["mapped_from"], df["reject_reason"] = res[0], res[1], res[2]

    rej = df[df["ticker"].isna()].copy()
    keep = df[df["ticker"].notna()].copy()

    # repeats: same ticker + same headline -> keep the first date
    keep = keep.sort_values(["date", "time", "alert_id"])
    key_cols = ["ticker", "top_headline"]
    keep["times_seen"] = keep.groupby(key_cols, dropna=False)["alert_id"].transform("count")
    dup = keep.duplicated(subset=key_cols, keep="first") & keep["top_headline"].notna()
    rep = keep[dup].copy()
    rep["reject_reason"] = "repeat_of_earlier_alert"
    keep = keep[~dup].copy()
    rej = pd.concat([rej, rep])

    keep["headline_direction"] = keep.apply(
        lambda r: headline_direction(r, ticker_to_alias.get(r["ticker"], []), rules), axis=1)
    keep["label_status"] = keep.apply(
        lambda r: "n/a" if r["headline_direction"] == "n/a"
        else "unclear" if r["headline_direction"] == "unclear"
        else "match" if r["headline_direction"] == r["type"] else "mismatch", axis=1)

    same = keep.groupby(["ticker", "date"])["type"].transform("nunique") > 1
    keep["same_day_conflict"] = same
    keep["company_clean"] = keep["company_norm"]
    keep["score_avg"] = keep["reasoning"].map(parse_score)
    for c in ["confidence", "article_count"]:
        keep[c] = pd.to_numeric(keep[c], errors="coerce")

    cols = ["alert_id", "date", "time", "ticker", "company", "mapped_from", "type", "confidence",
            "article_count", "score_avg", "market_mood", "top_headline", "headline_direction",
            "label_status", "times_seen", "same_day_conflict"]
    keep = keep.rename(columns={"type": "type"})[cols].sort_values(["date", "time", "ticker"])
    keep["date"] = keep["date"].dt.date
    keep.to_csv(out / "clean_alerts.csv", index=False)
    rej_cols = ["alert_id", "date", "time", "company", "type", "top_headline", "reject_reason"]
    rej["date"] = rej["date"].dt.date
    rej[rej_cols].sort_values("alert_id").to_csv(out / "rejected_alerts.csv", index=False)

    lab = keep["label_status"].value_counts()
    judged = lab.get("match", 0) + lab.get("mismatch", 0)
    lines = [
        "# Cleaning report", "",
        f"- Alerts in file: {n_all}",
        f"- Signal alerts (rise/fall/buy): {n_sig}",
        f"- In date range {rules['date_start']} to {rules['date_end']}: {n_range}",
        f"- Rejected (not a listed stock): {int((rej.reject_reason != 'repeat_of_earlier_alert').sum())}",
        f"- Rejected (repeat headline): {len(rep)}",
        f"- **Clean alerts: {len(keep)}** across {keep['ticker'].nunique()} tickers",
        f"- Mapped from company field: {(keep.mapped_from == 'company_field').sum()}, from headline: {(keep.mapped_from == 'headline').sum()}", "",
        "## Reject reasons", rej["reject_reason"].value_counts().to_string(), "",
        "## Label check (alert type vs headline direction)", lab.to_string(), "",
        f"Mismatch rate among clear headlines: {lab.get('mismatch', 0)}/{judged} = {lab.get('mismatch', 0) / max(judged, 1):.1%}",
        f"Same-day conflicts (same stock, opposite alerts): {int(keep['same_day_conflict'].sum())}",
    ]
    (out / "cleaning_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
