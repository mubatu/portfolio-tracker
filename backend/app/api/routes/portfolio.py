from typing import Annotated
from fastapi import APIRouter, Depends, Path, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps import CurrentUser
from app.db import get_db
from app.services.portfolio_service import backfill_portfolio_prices

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


@router.get("/{portfolio_id}/analyze")
async def analyze_portfolio(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    portfolio_id: int = Path(..., description="The portfolio ID to analyze"),
):
    """
    Analyze a portfolio:
      Step 1 — backfill market_prices for every holding.
      Step 2 — (TODO) calculate profit/loss.
    """
    # Verify the portfolio belongs to the current user
    row = db.execute(
        text("SELECT id FROM portfolios WHERE id = :pid AND user_id = :uid"),
        {"pid": portfolio_id, "uid": str(current_user.id)},
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    # Step 1: backfill prices
    backfill_result = backfill_portfolio_prices(db, portfolio_id)

    return {
        "portfolio_id": portfolio_id,
        "backfill": backfill_result,
    }
