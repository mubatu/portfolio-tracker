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


def calculate_portfolio_pl(db: Session, portfolio_id: int) -> dict:
    """Calculate profit/loss for every ticker in the portfolio.

    Uses the **average cost** method.
    Tracks *pocket* (money from outside) vs *safe* (reinvested proceeds)
    across the whole portfolio chronologically.

    A single ticker can appear in *both* current_holdings (if shares are
    still held) and closed_positions (if any shares were sold).
    """
    tickers = _distinct_tickers(db, portfolio_id)
    if not tickers:
        return {
            "current_holdings": [],
            "closed_positions": [],
            "totals": _empty_totals(),
        }

    current_holdings: list[dict] = []
    closed_positions: list[dict] = []

    for ticker in tickers:
        result = _ticker_pl(db, portfolio_id, ticker)

        # If there was any realized P/L, show in closed positions
        if result["total_sold_value"] > 0:
            invested_in_sold = result["total_sold_cost"]
            realized = result["realized_pl"]
            realized_pct = (
                float(realized / Decimal(str(invested_in_sold)) * 100)
                if invested_in_sold > 0
                else 0.0
            )
            closed_positions.append({
                "ticker": ticker,
                "total_invested": float(invested_in_sold),
                "total_returned": float(result["total_sold_value"]),
                "realized_pl": float(realized),
                "realized_pl_pct": round(realized_pct, 2),
            })

        # If shares are still held, show in current holdings
        if result["quantity"] > 0:
            unrealized_pct = (
                float(
                    Decimal(str(result["unrealized_pl"]))
                    / Decimal(str(result["current_cost_basis"]))
                    * 100
                )
                if result["current_cost_basis"] > 0
                else 0.0
            )
            current_holdings.append({
                "ticker": ticker,
                "quantity": float(result["quantity"]),
                "avg_cost": float(result["avg_cost"]),
                "current_price": float(result["current_price"]) if result["current_price"] else None,
                "current_value": float(result["current_value"]),
                "cost_basis": float(result["current_cost_basis"]),
                "unrealized_pl": float(result["unrealized_pl"]),
                "unrealized_pl_pct": round(unrealized_pct, 2),
            })

    pocket, safe = _portfolio_cash_flow(db, portfolio_id)
    totals = _aggregate_totals(current_holdings, closed_positions, pocket, safe)
    return {
        "current_holdings": current_holdings,
        "closed_positions": closed_positions,
        "totals": totals,
    }


# ------------------------------------------------------------------
# P/L helpers
# ------------------------------------------------------------------

def _ticker_pl(db: Session, portfolio_id: int, ticker: str) -> dict:
    """Compute P/L components for a single ticker using average cost.

    Returns raw data that the caller splits into current-holding
    and/or closed-position records.
    """
    rows = db.execute(
        text(
            """
            SELECT operation, quantity, price, date
            FROM transactions
            WHERE portfolio_id = :pid AND ticker = :ticker
            ORDER BY date, id
            """
        ),
        {"pid": portfolio_id, "ticker": ticker},
    ).fetchall()

    qty = Decimal(0)        # shares currently held
    cost_basis = Decimal(0) # total cost of held shares
    realized = Decimal(0)   # cumulative realized P/L
    total_sold_value = Decimal(0)  # total proceeds from sells
    total_sold_cost = Decimal(0)   # cost basis of sold shares

    for operation, quantity, price, txn_date in rows:
        q = Decimal(str(quantity))
        p = Decimal(str(price))

        if operation.lower() == "buy":
            cost_basis += q * p
            qty += q
        else:  # sell
            if qty > 0:
                avg_cost = cost_basis / qty
                sell_cost = q * avg_cost
                realized += q * (p - avg_cost)
                total_sold_value += q * p
                total_sold_cost += sell_cost
                cost_basis -= sell_cost
                qty -= q

    # Current (unrealized) valuation — use yesterday's close
    latest_price = _latest_price(db, ticker)
    current_value = Decimal(0)
    unrealized = Decimal(0)
    avg_cost_now = Decimal(0)

    if qty > 0:
        avg_cost_now = cost_basis / qty
        if latest_price is not None:
            current_value = qty * latest_price
            unrealized = qty * (latest_price - avg_cost_now)
        else:
            current_value = cost_basis

    return {
        "quantity": qty,
        "avg_cost": avg_cost_now,
        "current_price": latest_price,
        "current_value": current_value,
        "current_cost_basis": float(cost_basis),
        "unrealized_pl": unrealized,
        "realized_pl": realized,
        "total_sold_value": float(total_sold_value),
        "total_sold_cost": float(total_sold_cost),
    }


def _latest_price(db: Session, ticker: str) -> Decimal | None:
    """Get the most recent close price from market_prices (before today)."""
    row = db.execute(
        text(
            """
            SELECT close FROM market_prices
            WHERE ticker = :ticker AND date < CURRENT_DATE
            ORDER BY date DESC
            LIMIT 1
            """
        ),
        {"ticker": ticker},
    ).fetchone()
    return Decimal(str(row[0])) if row else None


def _aggregate_totals(
    current_holdings: list[dict],
    closed_positions: list[dict],
    pocket: Decimal,
    safe: Decimal,
) -> dict:
    """Build portfolio-wide totals using pocket/safe cash-flow model."""
    portfolio_value = sum(h["current_value"] for h in current_holdings)
    realized = sum(c["realized_pl"] for c in closed_positions)
    unrealized = sum(h["unrealized_pl"] for h in current_holdings)
    total_pl = realized + unrealized
    total_pl_pct = (
        float(total_pl / float(pocket) * 100) if pocket > 0 else 0.0
    )

    return {
        "total_invested": round(float(pocket), 2),
        "portfolio_value": round(portfolio_value, 2),
        "in_the_safe": round(float(safe), 2),
        "realized_pl": round(realized, 2),
        "unrealized_pl": round(unrealized, 2),
        "total_pl": round(total_pl, 2),
        "total_pl_pct": round(total_pl_pct, 2),
    }


def _empty_totals() -> dict:
    return {
        "total_invested": 0,
        "portfolio_value": 0,
        "in_the_safe": 0,
        "realized_pl": 0,
        "unrealized_pl": 0,
        "total_pl": 0,
        "total_pl_pct": 0,
    }


def _portfolio_cash_flow(
    db: Session, portfolio_id: int
) -> tuple[Decimal, Decimal]:
    """Track money from pocket vs money in the safe.

    Process *all* portfolio transactions chronologically.
    On buy  → use cash in safe first; only the remainder is from pocket.
    On sell → proceeds go into the safe.

    Returns ``(pocket, safe)``.
    """
    rows = db.execute(
        text(
            """
            SELECT operation, quantity, price
            FROM transactions
            WHERE portfolio_id = :pid
            ORDER BY date, id
            """
        ),
        {"pid": portfolio_id},
    ).fetchall()

    pocket = Decimal(0)
    safe = Decimal(0)

    for operation, quantity, price in rows:
        amount = Decimal(str(quantity)) * Decimal(str(price))
        if operation.lower() == "buy":
            from_safe = min(safe, amount)
            from_pocket = amount - from_safe
            safe -= from_safe
            pocket += from_pocket
        else:  # sell
            safe += amount

    return pocket, safe


# ------------------------------------------------------------------
# Internal helpers (backfill)
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
