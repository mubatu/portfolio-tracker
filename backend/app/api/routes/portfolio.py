from fastapi import APIRouter, Path
from app.api.deps import CurrentUser

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


@router.get("/{portfolio_id}/analyze")
async def analyze_portfolio(
    current_user: CurrentUser,
    portfolio_id: int = Path(..., description="The portfolio ID to analyze"),
):
    """
    Analyze a portfolio — returns performance metrics, holdings breakdown, etc.
    TODO: implement analysis logic.
    """
    return {
        "portfolio_id": portfolio_id,
        "status": "not_implemented",
        "message": "Analysis endpoint is not yet implemented.",
    }
