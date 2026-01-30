from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    UserResponse,
)
from app.services import email_exists
from app.api.deps import CurrentUser

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/check-email", response_model=EmailCheckResponse)
async def check_email(
    request: EmailCheckRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Check if an email address is already registered."""
    exists = email_exists(db, request.email)
    return EmailCheckResponse(exists=exists)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser):
    """
    Get the current authenticated user's profile.
    Requires a valid Supabase JWT token in Authorization header.
    """
    return current_user
