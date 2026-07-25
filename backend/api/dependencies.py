"""
backend/api/dependencies.py
============================
Shared FastAPI dependencies: DB session, API key auth, pagination.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.session import get_db


# ── Database ──────────────────────────────────────────────────────────────────

DBSession = Annotated[AsyncSession, Depends(get_db)]


# ── API Key Auth ──────────────────────────────────────────────────────────────

async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Validates the X-API-Key header.
    If settings.API_KEY is empty, auth is disabled (development mode).
    """
    if not settings.API_KEY:
        return  # Auth disabled — development mode
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key. Provide X-API-Key header.",
        )


AuthRequired = Annotated[None, Depends(verify_api_key)]


# ── Pagination ────────────────────────────────────────────────────────────────

@dataclass
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Items per page"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


Pagination = Annotated[PaginationParams, Depends(get_pagination)]


# ── Common filter params ──────────────────────────────────────────────────────

@dataclass
class TradeFilters:
    account: str | None
    symbol: str | None
    date_from: str | None
    date_to: str | None
    time_slot: str | None
    is_promoted: bool | None


def get_trade_filters(
    account: str | None = Query(default=None, description="Filter by account name"),
    symbol: str | None = Query(default=None, description="Filter by symbol (e.g. FDAXM26)"),
    date_from: str | None = Query(default=None, description="Start date YYYY-MM-DD (session_date)"),
    date_to: str | None = Query(default=None, description="End date YYYY-MM-DD (session_date)"),
    time_slot: str | None = Query(default=None, description="Filter by time slot HH:MM (NY)"),
    is_promoted: bool | None = Query(default=None, description="Filter to BH-FDR promoted trades only"),
) -> TradeFilters:
    return TradeFilters(
        account=account,
        symbol=symbol,
        date_from=date_from,
        date_to=date_to,
        time_slot=time_slot,
        is_promoted=is_promoted,
    )


TradeFiltersDep = Annotated[TradeFilters, Depends(get_trade_filters)]
