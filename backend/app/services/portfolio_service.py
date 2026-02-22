"""
Backfill market prices for a portfolio's holdings.

Logic per ticker:
1. Replay buy/sell transactions chronologically to find date ranges
   where the user holds ≥ 1 share.
2. For each range, download daily close prices from yfinance
   (always excluding today).
3. Before writing, detect stock splits from yfinance split events in
   the downloaded window. If a split is newer than the latest stored
   market-price date, delete stored prices for that ticker and
   re-insert the fresh data.
4. Insert with ON CONFLICT DO NOTHING so re-runs are safe.
"""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy import text
from sqlalchemy.orm import Session

SPLIT_PRICE_SCALE = Decimal("0.00000001")
SPLIT_QUANTITY_SCALE = Decimal("0.00000001")


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


def calculate_adjusted_transaction_price(
    ticker: str,
    price: Decimal,
    txn_date: date,
    as_of: date | None = None,
) -> tuple[Decimal, Decimal]:
    """Calculate split-adjusted transaction price as of the given date.

    Returns ``(adjusted_price, split_factor)`` where:
      - ``split_factor`` is the cumulative product of split ratios
        in ``(txn_date, as_of]``.
      - ``adjusted_price`` is ``price / split_factor``.
    """
    effective_as_of = as_of or date.today()
    split_events = _fetch_split_events(ticker)
    split_factor = _split_factor_between_dates(
        split_events, txn_date, effective_as_of
    )

    if split_factor <= 0:
        split_factor = Decimal(1)

    adjusted_price = price / split_factor if split_factor != 1 else price
    return _quantize_price(adjusted_price), split_factor


def calculate_adjusted_transaction_values(
    ticker: str,
    quantity: Decimal,
    price: Decimal,
    txn_date: date,
    as_of: date | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """Calculate split-adjusted quantity & price as of the given date."""
    effective_as_of = as_of or date.today()
    split_events = _fetch_split_events(ticker)
    split_factor = _split_factor_between_dates(
        split_events, txn_date, effective_as_of
    )

    if split_factor <= 0:
        split_factor = Decimal(1)

    adjusted_quantity = (
        quantity * split_factor if split_factor != 1 else quantity
    )
    adjusted_price = price / split_factor if split_factor != 1 else price
    return (
        _quantize_quantity(adjusted_quantity),
        _quantize_price(adjusted_price),
        split_factor,
    )


def refresh_portfolio_adjusted_prices(db: Session, portfolio_id: int) -> dict:
    """Refresh split-adjusted transaction fields for a portfolio."""
    rows = db.execute(
        text(
            """
            SELECT id, ticker, quantity, price, adjusted_quantity, adjusted_price, date
            FROM transactions
            WHERE portfolio_id = :pid
            ORDER BY ticker, date, id
            """
        ),
        {"pid": portfolio_id},
    ).fetchall()

    if not rows:
        return {
            "transactions_processed": 0,
            "transactions_updated": 0,
            "tickers_processed": 0,
        }

    as_of = date.today()
    split_cache: dict[str, list[tuple[date, Decimal]]] = {}
    updates: list[dict[str, Decimal | int]] = []

    for (
        txn_id,
        ticker,
        quantity,
        price,
        adjusted_quantity,
        adjusted_price,
        txn_date,
    ) in rows:
        base_quantity = Decimal(str(quantity))
        base_price = Decimal(str(price))
        split_events = split_cache.get(ticker)
        if split_events is None:
            split_events = _fetch_split_events(ticker)
            split_cache[ticker] = split_events

        split_factor = _split_factor_between_dates(split_events, txn_date, as_of)
        new_adjusted_quantity = (
            base_quantity * split_factor if split_factor != 1 else base_quantity
        )
        new_adjusted_quantity = _quantize_quantity(new_adjusted_quantity)
        new_adjusted_price = (
            base_price / split_factor if split_factor != 1 else base_price
        )
        new_adjusted_price = _quantize_price(new_adjusted_price)

        current_adjusted_quantity = (
            _quantize_quantity(Decimal(str(adjusted_quantity)))
            if adjusted_quantity is not None
            else None
        )
        current_adjusted_price = (
            _quantize_price(Decimal(str(adjusted_price)))
            if adjusted_price is not None
            else None
        )
        if (
            current_adjusted_quantity == new_adjusted_quantity
            and current_adjusted_price == new_adjusted_price
        ):
            continue

        updates.append(
            {
                "id": int(txn_id),
                "adjusted_quantity": new_adjusted_quantity,
                "adjusted_price": new_adjusted_price,
            }
        )

    updated_count = 0
    if updates:
        result = db.execute(
            text(
                """
                UPDATE transactions
                SET adjusted_quantity = :adjusted_quantity,
                    adjusted_price = :adjusted_price
                WHERE id = :id
                """
            ),
            updates,
        )
        db.commit()
        if result.rowcount is None or result.rowcount < 0:
            updated_count = len(updates)
        else:
            updated_count = result.rowcount

    return {
        "transactions_processed": len(rows),
        "transactions_updated": updated_count,
        "tickers_processed": len(split_cache),
    }


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
            SELECT operation, COALESCE(adjusted_quantity, quantity), COALESCE(adjusted_price, price), date
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

    for operation, effective_quantity, effective_price, txn_date in rows:
        q = Decimal(str(effective_quantity))
        p = Decimal(str(effective_price))

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
            SELECT operation, COALESCE(adjusted_quantity, quantity), COALESCE(adjusted_price, price)
            FROM transactions
            WHERE portfolio_id = :pid
            ORDER BY date, id
            """
        ),
        {"pid": portfolio_id},
    ).fetchall()

    pocket = Decimal(0)
    safe = Decimal(0)

    for operation, effective_quantity, price in rows:
        quantity = effective_quantity
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
            SELECT operation, COALESCE(adjusted_quantity, quantity), date
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
    """Detect new splits in the downloaded window and refresh ticker prices."""
    if fresh_prices.empty:
        return

    window_start = fresh_prices["date"].min()
    window_end = fresh_prices["date"].max()

    split_events = _fetch_split_events(ticker)
    if not split_events:
        return

    in_window_splits = [
        split_date
        for split_date, _ in split_events
        if window_start <= split_date <= window_end
    ]
    if not in_window_splits:
        return

    # Find the latest date for this ticker that we already have in the DB
    row = db.execute(
        text(
            """
            SELECT date FROM market_prices
            WHERE ticker = :ticker
            ORDER BY date DESC
            LIMIT 1
            """
        ),
        {"ticker": ticker},
    ).fetchone()

    if row is None:
        return  # Nothing stored yet — no split check needed

    latest_stored_date = row[0]

    if any(split_date > latest_stored_date for split_date in in_window_splits):
        # New split detected — wipe and let the caller re-insert
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


def _fetch_split_events(ticker: str) -> list[tuple[date, Decimal]]:
    """Return ticker split events as ``(split_date, ratio)``."""
    try:
        split_series = yf.Ticker(ticker).splits
    except Exception:
        return []

    if split_series is None or split_series.empty:
        return []

    split_events: list[tuple[date, Decimal]] = []
    for split_ts, split_ratio in split_series.items():
        if pd.isna(split_ratio):
            continue

        ratio = Decimal(str(split_ratio))
        if ratio <= 0:
            continue

        split_dt = pd.to_datetime(split_ts, errors="coerce")
        if pd.isna(split_dt):
            continue

        split_events.append((split_dt.date(), ratio))

    split_events.sort(key=lambda x: x[0])
    return split_events


def _split_factor_between_dates(
    split_events: list[tuple[date, Decimal]],
    start_date: date,
    end_date: date,
) -> Decimal:
    """Cumulative split factor for ``(start_date, end_date]``."""
    if end_date <= start_date or not split_events:
        return Decimal(1)

    factor = Decimal(1)
    for split_date, ratio in split_events:
        if start_date < split_date <= end_date:
            factor *= ratio
    return factor


def _quantize_price(value: Decimal) -> Decimal:
    """Keep adjusted prices stable across refreshes."""
    return value.quantize(SPLIT_PRICE_SCALE)


def _quantize_quantity(value: Decimal) -> Decimal:
    """Keep adjusted quantities stable across refreshes."""
    return value.quantize(SPLIT_QUANTITY_SCALE)
