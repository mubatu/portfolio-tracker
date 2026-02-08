"""
Backfill market prices for a portfolio's holdings.

Logic per ticker:
1. Replay buy/sell transactions chronologically to find date ranges
   where the user holds ≥ 1 share.
2. For each range, download daily close prices from yfinance
   (always excluding today).
3. Before writing, detect stock splits: compare the DB price for the
   last transaction day before today against the yfinance price.
   If they differ → delete all stored prices for that ticker and
   re-insert the fresh (split-adjusted) data.
4. Insert with ON CONFLICT DO NOTHING so re-runs are safe.
"""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.orm import Session


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def backfill_portfolio_prices(db: Session, portfolio_id: int) -> dict:
    """Download & store missing market prices for every ticker in the portfolio.

    Returns a short summary dict (ticker → number of rows written).
    """
    tickers = _distinct_tickers(db, portfolio_id)
    if not tickers:
        return {"tickers_processed": 0}

    summary: dict[str, int] = {}

    for ticker in tickers:
        hold_ranges = _holding_ranges(db, portfolio_id, ticker)
        if not hold_ranges:
            summary[ticker] = 0
            continue

        # Merge ranges into one yfinance download window
        dl_start = min(r[0] for r in hold_ranges)
        dl_end = max(r[1] for r in hold_ranges)

        prices = _download_prices(ticker, dl_start, dl_end)
        if prices.empty:
            summary[ticker] = 0
            continue

        # Keep only dates that fall inside a holding range
        prices = _filter_to_ranges(prices, hold_ranges)
        if prices.empty:
            summary[ticker] = 0
            continue

        # Split detection
        _handle_split_detection(db, ticker, prices)

        # Upsert rows
        written = _upsert_prices(db, ticker, prices)
        summary[ticker] = written

    return {"tickers_processed": len(tickers), "details": summary}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _distinct_tickers(db: Session, portfolio_id: int) -> list[str]:
    rows = db.execute(
        text("SELECT DISTINCT ticker FROM transactions WHERE portfolio_id = :pid"),
        {"pid": portfolio_id},
    ).fetchall()
    return [r[0] for r in rows]


def _holding_ranges(
    db: Session, portfolio_id: int, ticker: str
) -> list[tuple[date, date]]:
    """Return a list of [start, end] date pairs where quantity held ≥ 1.

    ``end`` is capped at yesterday (today is always excluded).
    """
    rows = db.execute(
        text(
            """
            SELECT operation, quantity, date
            FROM transactions
            WHERE portfolio_id = :pid AND ticker = :ticker
            ORDER BY date
            """
        ),
        {"pid": portfolio_id, "ticker": ticker},
    ).fetchall()

    yesterday = date.today() - timedelta(days=1)
    qty = Decimal(0)
    ranges: list[tuple[date, date]] = []
    range_start: date | None = None

    for operation, quantity, txn_date in rows:
        prev_qty = qty
        if operation.lower() == "buy":
            qty += Decimal(str(quantity))
        else:
            qty -= Decimal(str(quantity))

        # Crossed from 0 → positive
        if prev_qty <= 0 < qty and range_start is None:
            range_start = txn_date

        # Crossed from positive → 0
        if prev_qty > 0 and qty <= 0 and range_start is not None:
            end = min(txn_date, yesterday)
            if range_start <= end:
                ranges.append((range_start, end))
            range_start = None

    # Still holding → range extends to yesterday
    if qty > 0 and range_start is not None:
        if range_start <= yesterday:
            ranges.append((range_start, yesterday))

    return ranges


def _download_prices(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Download daily close prices from yfinance.

    Returns a DataFrame with columns ``date`` and ``close``.
    ``end`` is *inclusive* in our semantics; yfinance ``end`` is exclusive,
    so we add one day.
    """
    yf_end = end + timedelta(days=1)
    try:
        df = yf.download(ticker, start=str(start), end=str(yf_end), progress=False)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Flatten MultiIndex columns that yfinance sometimes returns
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel("Ticker", axis=1)

    df = df.reset_index()
    df = df[["Date", "Close"]].dropna(subset=["Close"])
    df = df.rename(columns={"Date": "date", "Close": "close"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["close"] = df["close"].apply(lambda x: round(float(x), 2))

    # Exclude today
    today = date.today()
    df = df[df["date"] < today]
    return df


def _filter_to_ranges(
    prices: pd.DataFrame, ranges: list[tuple[date, date]]
) -> pd.DataFrame:
    """Keep only rows whose date falls inside at least one holding range."""
    mask = pd.Series(False, index=prices.index)
    for rng_start, rng_end in ranges:
        mask |= (prices["date"] >= rng_start) & (prices["date"] <= rng_end)
    return prices[mask].reset_index(drop=True)


def _handle_split_detection(
    db: Session, ticker: str, fresh_prices: pd.DataFrame
) -> None:
    """If the most-recent stored price differs from yfinance, assume a split
    and delete all stored prices for this ticker so they get re-inserted.
    """
    # Find the last date for this ticker that we already have in the DB
    row = db.execute(
        text(
            """
            SELECT date, close FROM market_prices
            WHERE ticker = :ticker
            ORDER BY date DESC
            LIMIT 1
            """
        ),
        {"ticker": ticker},
    ).fetchone()

    if row is None:
        return  # Nothing stored yet — no split check needed

    stored_date, stored_close = row[0], float(row[1])

    # Find the same date in the fresh data
    match = fresh_prices[fresh_prices["date"] == stored_date]
    if match.empty:
        return  # That date isn't in our download window — skip check

    yf_close = float(match.iloc[0]["close"])

    # Allow tiny float tolerance
    if abs(stored_close - yf_close) > 0.02:
        # Split detected — wipe and let the caller re-insert
        db.execute(
            text("DELETE FROM market_prices WHERE ticker = :ticker"),
            {"ticker": ticker},
        )
        db.commit()


def _upsert_prices(db: Session, ticker: str, prices: pd.DataFrame) -> int:
    """Insert prices with ON CONFLICT DO NOTHING. Returns rows actually written."""
    if prices.empty:
        return 0

    values = [
        {"ticker": ticker, "date": r["date"], "close": r["close"]}
        for _, r in prices.iterrows()
    ]

    result = db.execute(
        text(
            """
            INSERT INTO market_prices (ticker, date, close)
            VALUES (:ticker, :date, :close)
            ON CONFLICT (ticker, date) DO NOTHING
            """
        ),
        values,
    )
    db.commit()
    return result.rowcount
