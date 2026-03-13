from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "User"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    emailVerified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Account(Base):
    __tablename__ = "Account"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    userId: Mapped[str] = mapped_column(String, ForeignKey("User.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    providerAccountId: Mapped[str] = mapped_column(String, nullable=False)
    accessToken: Mapped[str | None] = mapped_column(Text, nullable=True)
    refreshToken: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiresAt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokenType: Mapped[str | None] = mapped_column(String, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(lazy="joined")

    __table_args__ = (Index("ix_account_provider_account", "provider", "providerAccountId", unique=True),)


class Session(Base):
    __tablename__ = "Session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    userId: Mapped[str] = mapped_column(String, ForeignKey("User.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    expiresAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(lazy="joined")


class QueryRun(Base):
    __tablename__ = "QueryRun"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    userId: Mapped[str | None] = mapped_column(
        String, ForeignKey("User.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversationId: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running", index=True)
    totalSteps: Mapped[int] = mapped_column(Integer, default=0)
    durationMs: Mapped[int] = mapped_column(Integer, default=0)
    promptTokens: Mapped[int] = mapped_column(Integer, default=0)
    completionTokens: Mapped[int] = mapped_column(Integer, default=0)
    estimatedCost: Mapped[float] = mapped_column(Float, default=0.0)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    steps: Mapped[list["QueryStep"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    user: Mapped["User | None"] = relationship(lazy="joined")


class QueryStep(Base):
    __tablename__ = "QueryStep"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    runId: Mapped[str] = mapped_column(
        String, ForeignKey("QueryRun.id", ondelete="CASCADE"), index=True, nullable=False
    )
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    tool: Mapped[str | None] = mapped_column(String, nullable=True)
    args: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool | None] = mapped_column(nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    durationMs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped["QueryRun"] = relationship(lazy="joined")

