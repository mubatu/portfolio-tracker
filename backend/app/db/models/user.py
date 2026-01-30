import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.session import Base


class Profile(Base):
    """
    Profile table following Supabase pattern.
    References auth.users(id) managed by Supabase.
    """
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True)  # References auth.users.id
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255))
    avatar_url = Column(Text)
    bio = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Profile {self.email}>"
